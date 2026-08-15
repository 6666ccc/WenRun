package com.wenrun.util;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 业务单号生成
 */
public final class BizNoUtil {

    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    private BizNoUtil() {
    }

    public static String next(String prefix) {
        int rnd = ThreadLocalRandom.current().nextInt(1000, 9999);
        return prefix + LocalDateTime.now().format(FMT) + rnd;
    }
}
