package com.wenrun.service;

import com.wenrun.entity.Drug;

import java.util.List;

public interface DrugService {
    List<Drug> list(String keyword, Integer status);
    Drug getById(Long id);
    Long create(Drug drug);
    void update(Drug drug);
}
