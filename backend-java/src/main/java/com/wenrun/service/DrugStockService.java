package com.wenrun.service;

import com.wenrun.vo.DrugStockVO;

import java.util.List;

public interface DrugStockService {
    List<DrugStockVO> list(Boolean lowStockOnly);
}
