package com.wenrun.ai.controller;

import com.wenrun.ai.service.AiPatientMemoryService;
import com.wenrun.ai.vo.AiMemoryWriteRequest;
import com.wenrun.common.Result;
import com.wenrun.entity.AiPatientMemory;
import com.wenrun.service.PatientAccessService;
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
    private final PatientAccessService patientAccess;

    @GetMapping
    public Result<List<AiPatientMemory>> list(@RequestParam(required = false) Long patientId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return Result.success(memoryService.listManageable(patientAccess.resolvePatientId(patientId), page, size));
    }

    @PutMapping("/{memoryId}")
    public Result<AiPatientMemory> update(@PathVariable String memoryId,
            @RequestParam(required = false) Long patientId,
            @Valid @RequestBody AiMemoryWriteRequest request) {
        return Result.success(memoryService.update(patientAccess.resolvePatientId(patientId), memoryId, request));
    }

    @PostMapping("/{memoryId}/confirm")
    public Result<Void> confirm(@PathVariable String memoryId,
            @RequestParam(required = false) Long patientId) {
        memoryService.confirm(patientAccess.resolvePatientId(patientId), memoryId);
        return Result.success();
    }

    @DeleteMapping("/{memoryId}")
    public Result<Void> delete(@PathVariable String memoryId,
            @RequestParam(required = false) Long patientId) {
        memoryService.delete(patientAccess.resolvePatientId(patientId), memoryId);
        return Result.success();
    }
}
