package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.dto.ChargePayDTO;
import com.wenrun.service.ChargeService;
import com.wenrun.vo.ChargeOrderVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 收费接口 — 收费单查询、生成与收款
 */
@RestController
@RequestMapping("/api/charges")
@RequiredArgsConstructor
public class ChargeController {

  private final ChargeService chargeService;

  @GetMapping
  public Result<List<ChargeOrderVO>> list(@RequestParam(required = false) Integer payStatus,
      @RequestParam(required = false) Long patientId) {
    return Result.success(chargeService.list(payStatus, patientId));
  }

  @GetMapping("/pending")
  public Result<List<ChargeOrderVO>> pending() {
    return Result.success(chargeService.list(BizStatus.PAY_PENDING, null));
  }

  @GetMapping("/{id}")
  public Result<ChargeOrderVO> get(@PathVariable Long id) {
    return Result.success(chargeService.getById(id));
  }

  @PostMapping("/from-visit/{visitId}")
  public Result<Long> createFromVisit(@PathVariable Long visitId) {
    return Result.success(chargeService.createFromVisit(visitId));
  }

  @PostMapping("/{id}/pay")
  public Result<Void> pay(@PathVariable Long id, @Valid @RequestBody ChargePayDTO dto) {
    chargeService.pay(id, dto);
    return Result.success();
  }
}
