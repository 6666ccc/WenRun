package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class DashboardVO {
    private long todayRegistrations;
    private long todayVisits;
    private long todayCharges;
    private BigDecimal todayRevenue;
    private long pendingDispense;
    private long lowStockDrugs;
}
