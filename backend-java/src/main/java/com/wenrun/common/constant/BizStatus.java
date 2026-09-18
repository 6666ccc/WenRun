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

    /** 启用 */
    public static final int ENABLED = 1;
    /** 停用 */
    public static final int DISABLED = 0;

    private BizStatus() {
    }
}
