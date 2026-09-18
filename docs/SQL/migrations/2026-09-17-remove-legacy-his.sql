-- 移除已下线的传统 HIS 表
--
-- 仅适用于代码已经升级到 2026-09-17 轻量版本的现有数据库。
-- MySQL DDL 会隐式提交；执行前必须完成整库备份并核对当前 DATABASE()。
-- 本脚本不会删除账号、患者、科室/专家、号源、挂号或任何 AI Agent 数据。

SELECT DATABASE() AS target_database;

DROP TABLE IF EXISTS charge_detail;
DROP TABLE IF EXISTS charge_order;
DROP TABLE IF EXISTS dispense_record;
DROP TABLE IF EXISTS prescription_item;
DROP TABLE IF EXISTS prescription;
DROP TABLE IF EXISTS drug_stock;
DROP TABLE IF EXISTS drug;
DROP TABLE IF EXISTS exam_request;
DROP TABLE IF EXISTS medical_item;
DROP TABLE IF EXISTS outpatient_visit;

