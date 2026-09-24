package com.wenrun.vo;

import lombok.Data;

/**
 * 运动或睡眠的可选项。
 */
@Data
public class ActivityOptionVO {

    private String code;
    private String name;

    public static ActivityOptionVO of(String code, String name) {
        ActivityOptionVO vo = new ActivityOptionVO();
        vo.setCode(code);
        vo.setName(name);
        return vo;
    }
}
