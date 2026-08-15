package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.service.DrugStockService;
import com.wenrun.vo.DrugStockVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 药品库存接口
 */
@RestController
@RequestMapping("/api/drug-stocks")
@RequiredArgsConstructor
public class DrugStockController {

  private final DrugStockService drugStockService;

  @GetMapping
  public Result<List<DrugStockVO>> list(@RequestParam(required = false) Boolean lowStockOnly) {
    return Result.success(drugStockService.list(lowStockOnly));
  }
}
