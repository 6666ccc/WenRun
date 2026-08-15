package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.entity.Dept;
import com.wenrun.service.DeptService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 科室接口
 */
@RestController
@RequestMapping("/api/depts")
@RequiredArgsConstructor
public class DeptController {

  private final DeptService deptService;

  @GetMapping
  public Result<List<Dept>> list(@RequestParam(required = false) Integer status) {
    return Result.success(deptService.list(status));
  }

  @GetMapping("/{id}")
  public Result<Dept> get(@PathVariable Long id) {
    return Result.success(deptService.getById(id));
  }

  @PostMapping
  public Result<Long> create(@RequestBody Dept dept) {
    return Result.success(deptService.create(dept));
  }

  @PutMapping("/{id}")
  public Result<Void> update(@PathVariable Long id, @RequestBody Dept dept) {
    dept.setId(id);
    deptService.update(dept);
    return Result.success();
  }
}
