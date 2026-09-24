package com.wenrun.service;

import com.wenrun.dto.ExerciseRecordDTO;
import com.wenrun.dto.SleepRecordDTO;
import com.wenrun.vo.ActivityOptionsVO;
import com.wenrun.vo.ActivitySummaryVO;
import com.wenrun.vo.ExerciseRecordVO;
import com.wenrun.vo.SleepRecordVO;

import java.util.List;

public interface ActivityRecordService {

    ActivityOptionsVO options();

    ActivitySummaryVO summary(Long patientId, Integer range);

    List<ExerciseRecordVO> listExercises(Long patientId, Integer limit);

    ExerciseRecordVO getExercise(Long patientId, Long id);

    ExerciseRecordVO createExercise(Long patientId, ExerciseRecordDTO dto);

    ExerciseRecordVO updateExercise(Long patientId, Long id, ExerciseRecordDTO dto);

    void deleteExercise(Long patientId, Long id);

    List<SleepRecordVO> listSleep(Long patientId, Integer limit);

    SleepRecordVO getSleep(Long patientId, Long id);

    SleepRecordVO createSleep(Long patientId, SleepRecordDTO dto);

    SleepRecordVO updateSleep(Long patientId, Long id, SleepRecordDTO dto);

    void deleteSleep(Long patientId, Long id);
}
