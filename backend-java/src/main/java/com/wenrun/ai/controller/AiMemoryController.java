package com.wenrun.ai.controller;

import com.wenrun.ai.service.AiPatientMemoryService;
import com.wenrun.ai.vo.AiMemoryWriteRequest;
import com.wenrun.common.Result;
import com.wenrun.common.ResultCode;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiPatientMemory;
import com.wenrun.entity.Patient;
import com.wenrun.repository.PatientRepository;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/ai/memories")
@RequiredArgsConstructor
public class AiMemoryController {
    private final AiPatientMemoryService memoryService;
    private final PatientRepository patientRepository;

    @GetMapping
    public Result<List<AiPatientMemory>> list(@RequestParam(defaultValue = "0") int page,
                                              @RequestParam(defaultValue = "20") int size) {
        return Result.success(memoryService.listManageable(currentPatientId(), page, size));
    }

    @PutMapping("/{memoryId}")
    public Result<AiPatientMemory> update(@PathVariable String memoryId,
                                          @Valid @RequestBody AiMemoryWriteRequest request) {
        return Result.success(memoryService.update(currentPatientId(), memoryId, request));
    }

    @PostMapping("/{memoryId}/confirm")
    public Result<Void> confirm(@PathVariable String memoryId) {
        memoryService.confirm(currentPatientId(), memoryId);
        return Result.success();
    }

    @DeleteMapping("/{memoryId}")
    public Result<Void> delete(@PathVariable String memoryId) {
        memoryService.delete(currentPatientId(), memoryId);
        return Result.success();
    }

    private Long currentPatientId() {
        Patient patient = patientRepository.selectByUserId(UserContext.getUserId());
        if (patient == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "当前账号还没有绑定患者档案");
        }
        return patient.getId();
    }
}
