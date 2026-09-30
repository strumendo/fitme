package io.github.strumendo.fitme.companion

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * The payload contract fitme ingests (`src/fitme/samsung.py`, schema_version 1).
 * Field names are the wire names; keep both sides in sync.
 */
@Serializable
data class Payload(
    @SerialName("schema_version") val schemaVersion: Int = SCHEMA_VERSION,
    @SerialName("exported_at") val exportedAt: String,
    @SerialName("steps_daily") val stepsDaily: List<StepsDaily>,
    @SerialName("heart_rate_daily") val heartRateDaily: List<HeartRateDaily>,
    val sleep: List<Sleep>,
    @SerialName("body_composition") val bodyComposition: List<BodyComposition>,
    val nutrition: List<Nutrition>,
    val water: List<Water>,
    val exercise: List<Exercise>,
) {
    fun counts(): Map<String, Int> = mapOf(
        "steps_daily" to stepsDaily.size,
        "heart_rate_daily" to heartRateDaily.size,
        "sleep" to sleep.size,
        "body_composition" to bodyComposition.size,
        "nutrition" to nutrition.size,
        "water" to water.size,
        "exercise" to exercise.size,
    )

    companion object {
        const val SCHEMA_VERSION = 1
    }
}

@Serializable
data class StepsDaily(
    val date: String,
    val steps: Long?,
    @SerialName("device_group") val deviceGroup: String? = null,
)

@Serializable
data class HeartRateDaily(
    val date: String,
    val min: Int?,
    val max: Int?,
    val avg: Int?,
    @SerialName("device_group") val deviceGroup: String? = null,
)

@Serializable
data class Sleep(
    val uid: String,
    @SerialName("start_time") val startTime: String,
    @SerialName("end_time") val endTime: String,
    @SerialName("duration_s") val durationS: Long?,
    @SerialName("sleep_score") val sleepScore: Int?,
    @SerialName("awake_s") val awakeS: Long?,
    @SerialName("light_s") val lightS: Long?,
    @SerialName("deep_s") val deepS: Long?,
    @SerialName("rem_s") val remS: Long?,
    @SerialName("device_group") val deviceGroup: String? = null,
)

@Serializable
data class BodyComposition(
    val uid: String,
    @SerialName("start_time") val startTime: String,
    @SerialName("weight_kg") val weightKg: Float?,
    @SerialName("body_fat_pct") val bodyFatPct: Float?,
    @SerialName("skeletal_muscle_mass_kg") val skeletalMuscleMassKg: Float?,
    @SerialName("muscle_mass_pct") val muscleMassPct: Float?,
    @SerialName("bmr_kcal") val bmrKcal: Float?,
    @SerialName("total_body_water_l") val totalBodyWaterL: Float?,
    val bmi: Float?,
    @SerialName("device_group") val deviceGroup: String? = null,
)

@Serializable
data class Nutrition(
    val uid: String,
    @SerialName("start_time") val startTime: String,
    val title: String?,
    @SerialName("meal_type") val mealType: String?,
    val kcal: Float?,
    @SerialName("protein_g") val proteinG: Float?,
    @SerialName("carbs_g") val carbsG: Float?,
    @SerialName("fat_g") val fatG: Float?,
    // Not typed columns on the fitme side — they land in raw_json.
    @SerialName("fiber_g") val fiberG: Float? = null,
    @SerialName("sugar_g") val sugarG: Float? = null,
    @SerialName("sodium_mg") val sodiumMg: Float? = null,
    @SerialName("device_group") val deviceGroup: String? = null,
)

@Serializable
data class Water(
    val uid: String,
    @SerialName("start_time") val startTime: String,
    @SerialName("amount_ml") val amountMl: Float?,
    @SerialName("device_group") val deviceGroup: String? = null,
)

@Serializable
data class Exercise(
    val uid: String,
    @SerialName("start_time") val startTime: String,
    @SerialName("end_time") val endTime: String?,
    @SerialName("exercise_type") val exerciseType: String?,
    @SerialName("custom_title") val customTitle: String?,
    @SerialName("duration_s") val durationS: Long?,
    val kcal: Float?,
    @SerialName("distance_m") val distanceM: Float?,
    @SerialName("mean_hr") val meanHr: Int?,
    @SerialName("max_hr") val maxHr: Int?,
    @SerialName("device_group") val deviceGroup: String? = null,
)

val PayloadJson = Json {
    encodeDefaults = true
    ignoreUnknownKeys = true
}

private val ISO_WITH_OFFSET: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ssXXX")

/**
 * ISO-8601 with the record's own offset (`2026-09-28T07:12:00-03:00`) — fitme
 * derives the local `date` from it. Falls back to the phone's current zone
 * when Samsung Health didn't store an offset.
 */
fun isoWithOffset(instant: Instant, offset: ZoneOffset?): String {
    val zone = offset ?: ZoneId.systemDefault().rules.getOffset(instant)
    return OffsetDateTime.ofInstant(instant, zone).format(ISO_WITH_OFFSET)
}
