package io.github.strumendo.fitme.companion

import android.app.Activity
import android.content.Context
import android.util.Log
import com.samsung.android.sdk.health.data.HealthDataService
import com.samsung.android.sdk.health.data.HealthDataStore
import com.samsung.android.sdk.health.data.data.HealthDataPoint
import com.samsung.android.sdk.health.data.device.DeviceGroup
import com.samsung.android.sdk.health.data.error.ResolvablePlatformException
import com.samsung.android.sdk.health.data.permission.AccessType
import com.samsung.android.sdk.health.data.permission.Permission
import com.samsung.android.sdk.health.data.request.AggregateRequest
import com.samsung.android.sdk.health.data.request.DataType
import com.samsung.android.sdk.health.data.request.DataTypes
import com.samsung.android.sdk.health.data.request.LocalDateFilter
import com.samsung.android.sdk.health.data.request.LocalDateGroup
import com.samsung.android.sdk.health.data.request.LocalDateGroupUnit
import com.samsung.android.sdk.health.data.request.LocalTimeFilter
import com.samsung.android.sdk.health.data.request.LocalTimeGroup
import com.samsung.android.sdk.health.data.request.LocalTimeGroupUnit
import com.samsung.android.sdk.health.data.request.Ordering
import com.samsung.android.sdk.health.data.request.ReadDataRequest
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import kotlin.math.roundToInt

/**
 * The only file that touches the Samsung Health Data SDK. Reads the seven
 * payload types for the given windows and maps them to the fitme contract.
 *
 * API names checked against the SDK 1.1.0 reference on developer.samsung.com
 * (not compiled here — the .aar isn't in git).
 */
class SamsungHealthReader(context: Context) {
    private val store: HealthDataStore = HealthDataService.getStore(context.applicationContext)
    private val deviceGroups = mutableMapOf<String, String?>()

    suspend fun hasPermissions(): Boolean =
        store.getGrantedPermissions(PERMISSIONS).containsAll(PERMISSIONS)

    suspend fun requestPermissions(activity: Activity): Boolean =
        store.requestPermissions(PERMISSIONS, activity).containsAll(PERMISSIONS)

    /**
     * Samsung Health missing / outdated / disabled comes back as a resolvable
     * exception — let the platform show its own fix-it screen.
     */
    fun tryResolve(activity: Activity, error: Throwable): Boolean {
        if (error is ResolvablePlatformException && error.hasResolution) {
            error.resolve(activity)
            return true
        }
        return false
    }

    suspend fun read(windows: Map<String, ReadWindow>): Payload = Payload(
        exportedAt = isoWithOffset(Instant.now(), null),
        stepsDaily = readStepsDaily(windows.getValue("steps_daily")),
        heartRateDaily = readHeartRateDaily(windows.getValue("heart_rate_daily")),
        sleep = readSleep(windows.getValue("sleep")),
        bodyComposition = readBodyComposition(windows.getValue("body_composition")),
        nutrition = readNutrition(windows.getValue("nutrition")),
        water = readWater(windows.getValue("water")),
        exercise = readExercise(windows.getValue("exercise")),
    )

    // Steps only exist as an aggregate.
    private suspend fun readStepsDaily(window: ReadWindow): List<StepsDaily> {
        val request = DataType.StepsType.TOTAL.requestBuilder
            .setLocalTimeFilterWithGroup(
                LocalTimeFilter.of(window.start, window.end),
                LocalTimeGroup.of(LocalTimeGroupUnit.DAILY, 1),
            )
            .setOrdering(Ordering.ASC)
            .build()
        return store.aggregateData(request).dataList.map { bucket ->
            StepsDaily(
                date = bucket.getStartLocalDateTime().toLocalDate().toString(),
                steps = bucket.value,
            )
        }
    }

    // MIN / MAX are daily aggregates; there is no average aggregate, so the
    // mean comes from the raw points of the same window.
    private suspend fun readHeartRateDaily(window: ReadWindow): List<HeartRateDaily> {
        val dateFilter = LocalDateFilter.of(window.start.toLocalDate(), window.end.toLocalDate())
        val daily = LocalDateGroup.of(LocalDateGroupUnit.DAILY, 1)

        suspend fun byDay(request: AggregateRequest<Float>): Map<LocalDate, Float> =
            store.aggregateData(request).dataList
                .mapNotNull { b -> b.value?.let { b.getStartLocalDateTime().toLocalDate() to it } }
                .toMap()

        val mins = byDay(
            DataType.HeartRateType.MIN.requestBuilder
                .setLocalDateFilterWithGroup(dateFilter, daily)
                .setOrdering(Ordering.ASC)
                .build()
        )
        val maxs = byDay(
            DataType.HeartRateType.MAX.requestBuilder
                .setLocalDateFilterWithGroup(dateFilter, daily)
                .setOrdering(Ordering.ASC)
                .build()
        )
        val avgs = readAll { DataTypes.HEART_RATE.readDataRequestBuilder.window(window) }
            .mapNotNull { p -> p.getValue(DataType.HeartRateType.HEART_RATE)?.let { localDate(p) to it } }
            .groupBy({ it.first }, { it.second })
            .mapValues { (_, bpm) -> bpm.average().roundToInt() }

        return (mins.keys + maxs.keys + avgs.keys).sorted().map { day ->
            HeartRateDaily(
                date = day.toString(),
                min = mins[day]?.roundToInt(),
                max = maxs[day]?.roundToInt(),
                avg = avgs[day],
            )
        }
    }

    private suspend fun readSleep(window: ReadWindow): List<Sleep> =
        readAll { DataTypes.SLEEP.readDataRequestBuilder.window(window) }.map { p ->
            val stageSeconds = mutableMapOf<DataType.SleepType.StageType, Long>()
            p.getValue(DataType.SleepType.SESSIONS).orEmpty().forEach { session ->
                session.stages.orEmpty().forEach { stage ->
                    val seconds = stage.endTime.epochSecond - stage.startTime.epochSecond
                    stageSeconds.merge(stage.stage, seconds) { a, b -> a + b }
                }
            }
            val end = p.endTime ?: p.startTime
            Sleep(
                uid = p.uid,
                startTime = isoWithOffset(p.startTime, p.zoneOffset),
                endTime = isoWithOffset(end, p.zoneOffset),
                durationS = p.getValue(DataType.SleepType.DURATION)?.seconds,
                sleepScore = p.getValue(DataType.SleepType.SLEEP_SCORE),
                awakeS = stageSeconds[DataType.SleepType.StageType.AWAKE],
                lightS = stageSeconds[DataType.SleepType.StageType.LIGHT],
                deepS = stageSeconds[DataType.SleepType.StageType.DEEP],
                remS = stageSeconds[DataType.SleepType.StageType.REM],
                deviceGroup = deviceGroup(p),
            )
        }

    private suspend fun readBodyComposition(window: ReadWindow): List<BodyComposition> =
        readAll { DataTypes.BODY_COMPOSITION.readDataRequestBuilder.window(window) }.map { p ->
            BodyComposition(
                uid = p.uid,
                startTime = isoWithOffset(p.startTime, p.zoneOffset),
                weightKg = p.getValue(DataType.BodyCompositionType.WEIGHT),
                bodyFatPct = p.getValue(DataType.BodyCompositionType.BODY_FAT),
                skeletalMuscleMassKg = p.getValue(DataType.BodyCompositionType.SKELETAL_MUSCLE_MASS),
                // MUSCLE_MASS is a percentage in the SDK, despite the name.
                muscleMassPct = p.getValue(DataType.BodyCompositionType.MUSCLE_MASS),
                bmrKcal = p.getValue(DataType.BodyCompositionType.BASAL_METABOLIC_RATE)?.toFloat(),
                totalBodyWaterL = p.getValue(DataType.BodyCompositionType.TOTAL_BODY_WATER),
                bmi = p.getValue(DataType.BodyCompositionType.BODY_MASS_INDEX),
                deviceGroup = deviceGroup(p),
            )
        }

    private suspend fun readNutrition(window: ReadWindow): List<Nutrition> =
        readAll { DataTypes.NUTRITION.readDataRequestBuilder.window(window) }.map { p ->
            Nutrition(
                uid = p.uid,
                startTime = isoWithOffset(p.startTime, p.zoneOffset),
                title = p.getValue(DataType.NutritionType.TITLE),
                mealType = p.getValue(DataType.NutritionType.MEAL_TYPE)?.name,
                kcal = p.getValue(DataType.NutritionType.CALORIES),
                proteinG = p.getValue(DataType.NutritionType.PROTEIN),
                carbsG = p.getValue(DataType.NutritionType.CARBOHYDRATE),
                fatG = p.getValue(DataType.NutritionType.TOTAL_FAT),
                fiberG = p.getValue(DataType.NutritionType.DIETARY_FIBER),
                sugarG = p.getValue(DataType.NutritionType.SUGAR),
                sodiumMg = p.getValue(DataType.NutritionType.SODIUM),
                deviceGroup = deviceGroup(p),
            )
        }

    private suspend fun readWater(window: ReadWindow): List<Water> =
        readAll { DataTypes.WATER_INTAKE.readDataRequestBuilder.window(window) }.map { p ->
            Water(
                uid = p.uid,
                startTime = isoWithOffset(p.startTime, p.zoneOffset),
                amountMl = p.getValue(DataType.WaterIntakeType.AMOUNT),
                deviceGroup = deviceGroup(p),
            )
        }

    // One exercise record can hold several sessions (e.g. an interval workout);
    // fitme gets one row with the totals.
    private suspend fun readExercise(window: ReadWindow): List<Exercise> =
        readAll { DataTypes.EXERCISE.readDataRequestBuilder.window(window) }.map { p ->
            val sessions = p.getValue(DataType.ExerciseType.SESSIONS).orEmpty()
            Exercise(
                uid = p.uid,
                startTime = isoWithOffset(p.startTime, p.zoneOffset),
                endTime = p.endTime?.let { isoWithOffset(it, p.zoneOffset) },
                exerciseType = p.getValue(DataType.ExerciseType.EXERCISE_TYPE)?.name,
                customTitle = p.getValue(DataType.ExerciseType.CUSTOM_TITLE),
                durationS = sessions.takeIf { it.isNotEmpty() }?.sumOf { it.duration.seconds },
                kcal = sessions.takeIf { it.isNotEmpty() }?.map { it.calories }?.sum(),
                distanceM = sessions.mapNotNull { it.distance }.takeIf { it.isNotEmpty() }?.sum(),
                meanHr = sessions.firstNotNullOfOrNull { it.meanHeartRate }?.roundToInt(),
                maxHr = sessions.mapNotNull { it.maxHeartRate }.maxOrNull()?.roundToInt(),
                deviceGroup = deviceGroup(p),
            )
        }

    private fun ReadDataRequest.DualTimeBuilder<HealthDataPoint>.window(window: ReadWindow) =
        setLocalTimeFilter(LocalTimeFilter.of(window.start, window.end)).setOrdering(Ordering.ASC)

    /** Follows `pageToken` until the SDK stops handing one back. */
    private suspend fun readAll(
        builder: () -> ReadDataRequest.DualTimeBuilder<HealthDataPoint>,
    ): List<HealthDataPoint> {
        val points = mutableListOf<HealthDataPoint>()
        var token: String? = null
        do {
            val request = builder().apply { token?.let { setPageToken(it) } }.build()
            val response = store.readData(request)
            points += response.dataList
            token = response.pageToken?.takeIf { it.isNotBlank() && it != token }
        } while (token != null)
        return points
    }

    private fun localDate(p: HealthDataPoint): LocalDate {
        val zone = p.zoneOffset ?: ZoneId.systemDefault()
        return p.startTime.atZone(zone).toLocalDate()
    }

    private suspend fun deviceGroup(p: HealthDataPoint): String? {
        val deviceId = p.dataSource?.deviceId ?: return null
        return deviceGroups.getOrPut(deviceId) {
            runCatching {
                (store.getDeviceManager().getDevice(deviceId)?.deviceType as? DeviceGroup)?.name
            }.onFailure { Log.w(TAG, "device lookup failed for $deviceId", it) }.getOrNull()
        }
    }

    private companion object {
        const val TAG = "SamsungHealthReader"

        val PERMISSIONS: Set<Permission> = setOf(
            DataTypes.STEPS,
            DataTypes.HEART_RATE,
            DataTypes.SLEEP,
            DataTypes.BODY_COMPOSITION,
            DataTypes.NUTRITION,
            DataTypes.WATER_INTAKE,
            DataTypes.EXERCISE,
        ).map { Permission.of(it, AccessType.READ) }.toSet()
    }
}
