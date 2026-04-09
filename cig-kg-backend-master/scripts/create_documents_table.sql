-- 创建documents表
DROP TABLE IF EXISTS `documents`;

CREATE TABLE `documents` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `name` VARCHAR(255) NOT NULL COMMENT '文档名称',
    `file_path` VARCHAR(500) NOT NULL COMMENT '文档路径',
    `pdf_path` VARCHAR(500) DEFAULT NULL COMMENT 'PDF文件路径',
    `json_file_path` VARCHAR(500) DEFAULT NULL COMMENT 'JSON文件路径',
    `image_file_path` VARCHAR(500) DEFAULT NULL COMMENT '图片文件路径',
    `status` TINYINT DEFAULT 0 COMMENT '状态：0-待审核，1-已审核，2-已删除',
    `upload_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    `update_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近更新时间',
    `upload_user` VARCHAR(255) DEFAULT NULL COMMENT '上传用户',
    `es_code` VARCHAR(255) DEFAULT NULL COMMENT '文件量化索引码',
    `file_size` INT DEFAULT NULL COMMENT '文件大小(bytes)',
    `file_type` VARCHAR(255) DEFAULT NULL COMMENT '文件类型: 经验库，维修库，操作库',

    -- 索引优化（根据常用查询字段建立）
    INDEX `idx_status` (`status`),
    INDEX `idx_name` (`name`),
    INDEX `idx_file_type` (`file_type`),
    INDEX `idx_upload_time` (`upload_time`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档治理表';

INSERT INTO `documents` (
    `name`, 
    `file_path`, 
    `pdf_path`, 
    `json_file_path`, 
    `image_file_path`, 
    `status`, 
    `upload_user`, 
    `es_code`, 
    `file_size`, 
    `file_type`
) VALUES 
(
    '卷烟生产工艺流程说明', 
    '/docs/source/production_process.docx', 
    '/docs/pdf/production_process.pdf',
    '/json/doc_001.json', 
    '/images/doc_001/', 
    1, -- 假设已审核
    'admin', 
    'ES_IDX_001',
    1024000, -- 约1MB
    '操作库'
),
(
    '设备维护手册_V2.0', 
    '/docs/source/equipment_maintenance.docx', 
    '/docs/pdf/equipment_maintenance.pdf',
    '/json/doc_002.json', 
    '/images/doc_002/', 
    1, 
    'engineer_01', 
    'ES_IDX_002',
    2048500, -- 约2MB
    '维修库'
),
(
    '2023年度质量检测报告', 
    '/docs/source/quality_standards.docx', 
    '/docs/pdf/quality_standards.pdf',
    '/json/doc_003.json', 
    '/images/doc_003/', 
    0, -- 待审核
    'qa_user', 
    NULL, -- 尚未生成索引
    512000, -- 约500KB
    '经验库'
);