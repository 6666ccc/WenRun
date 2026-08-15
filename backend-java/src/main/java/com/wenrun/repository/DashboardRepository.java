package com.wenrun.repository;

import org.apache.ibatis.annotations.Mapper;

import java.math.BigDecimal;

@Mapper
public interface DashboardRepository {

    long countTodayRegistrations();

    long countTodayVisits();

    long countTodayPaidCharges();

    BigDecimal sumTodayRevenue();

    long countPendingDispense();
}
