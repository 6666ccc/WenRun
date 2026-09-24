package com.wenrun.vo;

import lombok.Data;

import java.util.List;

/**
 * 运动睡眠录入可选项。
 */
@Data
public class ActivityOptionsVO {

    private List<ActivityOptionVO> exerciseTypes;
    private List<ActivityOptionVO> intensities;
    private List<ActivityOptionVO> sleepQualities;
}
