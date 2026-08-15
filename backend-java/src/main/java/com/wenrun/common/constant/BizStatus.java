package com.wenrun.common.constant;

/**
 * 业务状态常量
 */
public final class BizStatus {

    /** 挂号：已挂号 */
    public static final int REG_REGISTERED = 1;
    /** 挂号：已就诊 */
    public static final int REG_VISITED = 2;
    /** 挂号：已退号 */
    public static final int REG_CANCELLED = 3;

    /** 就诊：进行中 */
    public static final int VISIT_IN_PROGRESS = 1;
    /** 就诊：已完成 */
    public static final int VISIT_COMPLETED = 2;

    /** 处方：待缴费 */
    public static final int RX_PENDING_PAY = 1;
    /** 处方：已缴费 */
    public static final int RX_PAID = 2;
    /** 处方：已发药 */
    public static final int RX_DISPENSED = 3;
    /** 处方：已作废 */
    public static final int RX_CANCELLED = 4;

    /** 收费：待支付 */
    public static final int PAY_PENDING = 0;
    /** 收费：已支付 */
    public static final int PAY_PAID = 1;
    /** 收费：已退款 */
    public static final int PAY_REFUNDED = 2;

    /** 费用明细：挂号 */
    public static final int CHARGE_REG = 1;
    /** 费用明细：处方 */
    public static final int CHARGE_RX = 2;
    /** 费用明细：检查 */
    public static final int CHARGE_EXAM = 3;

    /** 检查申请：待缴费 */
    public static final int EXAM_PENDING_PAY = 1;
    /** 检查申请：已缴费 */
    public static final int EXAM_PAID = 2;

    /** 启用 */
    public static final int ENABLED = 1;
    /** 停用 */
    public static final int DISABLED = 0;

    private BizStatus() {
    }
}
