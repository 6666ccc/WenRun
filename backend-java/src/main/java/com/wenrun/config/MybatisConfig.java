package com.wenrun.config;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.context.annotation.Configuration;

@Configuration
@MapperScan("com.wenrun.repository")
public class MybatisConfig {
}
