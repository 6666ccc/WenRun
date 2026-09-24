package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.ExerciseRecordDTO;
import com.wenrun.dto.SleepRecordDTO;
import com.wenrun.service.ActivityRecordService;
import com.wenrun.vo.ActivityOptionsVO;
import com.wenrun.vo.ActivitySummaryVO;
import com.wenrun.vo.ExerciseRecordVO;
import com.wenrun.vo.SleepRecordVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 患者运动与睡眠手动记录。
 */
@RestController
@RequiredArgsConstructor
public class ActivityRecordController {

    private final ActivityRecordService activityRecordService;

    /** GET /api/activity/options — 运动类型、强度、睡眠质量，不属于某个患者 */
    @GetMapping("/api/activity/options")
    public Result<ActivityOptionsVO> options() {
        return Result.success(activityRecordService.options());
    }

    /** GET /api/patients/{patientId}/activity/summary?range=7 */
    @GetMapping("/api/patients/{patientId}/activity/summary")
    public Result<ActivitySummaryVO> summary(@PathVariable Long patientId,
                                             @RequestParam(required = false) Integer range) {
        return Result.success(activityRecordService.summary(patientId, range));
    }

    @GetMapping("/api/patients/{patientId}/exercises")
    public Result<List<ExerciseRecordVO>> listExercises(@PathVariable Long patientId,
                                                        @RequestParam(required = false) Integer limit) {
        return Result.success(activityRecordService.listExercises(patientId, limit));
    }

    @GetMapping("/api/patients/{patientId}/exercises/{id}")
    public Result<ExerciseRecordVO> getExercise(@PathVariable Long patientId, @PathVariable Long id) {
        return Result.success(activityRecordService.getExercise(patientId, id));
    }

    @PostMapping("/api/patients/{patientId}/exercises")
    public Result<ExerciseRecordVO> createExercise(@PathVariable Long patientId,
                                                   @RequestBody ExerciseRecordDTO dto) {
        return Result.success(activityRecordService.createExercise(patientId, dto));
    }

    @PutMapping("/api/patients/{patientId}/exercises/{id}")
    public Result<ExerciseRecordVO> updateExercise(@PathVariable Long patientId,
                                                   @PathVariable Long id,
                                                   @RequestBody ExerciseRecordDTO dto) {
        return Result.success(activityRecordService.updateExercise(patientId, id, dto));
    }

    @DeleteMapping("/api/patients/{patientId}/exercises/{id}")
    public Result<Void> deleteExercise(@PathVariable Long patientId, @PathVariable Long id) {
        activityRecordService.deleteExercise(patientId, id);
        return Result.success();
    }

    @GetMapping("/api/patients/{patientId}/sleep-records")
    public Result<List<SleepRecordVO>> listSleep(@PathVariable Long patientId,
                                                 @RequestParam(required = false) Integer limit) {
        return Result.success(activityRecordService.listSleep(patientId, limit));
    }

    @GetMapping("/api/patients/{patientId}/sleep-records/{id}")
    public Result<SleepRecordVO> getSleep(@PathVariable Long patientId, @PathVariable Long id) {
        return Result.success(activityRecordService.getSleep(patientId, id));
    }

    @PostMapping("/api/patients/{patientId}/sleep-records")
    public Result<SleepRecordVO> createSleep(@PathVariable Long patientId,
                                             @RequestBody SleepRecordDTO dto) {
        return Result.success(activityRecordService.createSleep(patientId, dto));
    }

    @PutMapping("/api/patients/{patientId}/sleep-records/{id}")
    public Result<SleepRecordVO> updateSleep(@PathVariable Long patientId,
                                             @PathVariable Long id,
                                             @RequestBody SleepRecordDTO dto) {
        return Result.success(activityRecordService.updateSleep(patientId, id, dto));
    }

    @DeleteMapping("/api/patients/{patientId}/sleep-records/{id}")
    public Result<Void> deleteSleep(@PathVariable Long patientId, @PathVariable Long id) {
        activityRecordService.deleteSleep(patientId, id);
        return Result.success();
    }
}
