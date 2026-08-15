package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.entity.MedicalItem;
import com.wenrun.service.MedicalItemService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 诊疗项目接口 — 检查/治疗等项目维护
 */
@RestController
@RequestMapping("/api/medical-items")
@RequiredArgsConstructor
public class MedicalItemController {

    private final MedicalItemService medicalItemService;

    /** GET /api/medical-items — 查询诊疗项目列表 */
    @GetMapping
    public Result<List<MedicalItem>> list(@RequestParam(required = false) Integer itemType,
                                          @RequestParam(required = false) Integer status) {
        return Result.success(medicalItemService.list(itemType, status));
    }

    /** GET /api/medical-items/{id} — 查询诊疗项目详情 */
    @GetMapping("/{id}")
    public Result<MedicalItem> get(@PathVariable Long id) {
        return Result.success(medicalItemService.getById(id));
    }

    /** POST /api/medical-items — 新建诊疗项目 */
    @PostMapping
    public Result<Long> create(@RequestBody MedicalItem item) {
        return Result.success(medicalItemService.create(item));
    }

    /** PUT /api/medical-items/{id} — 更新诊疗项目 */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody MedicalItem item) {
        item.setId(id);
        medicalItemService.update(item);
        return Result.success();
    }
}
