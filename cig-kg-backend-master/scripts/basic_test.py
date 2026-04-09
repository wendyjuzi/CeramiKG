# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# 基础后端功能测试
# """
# import sys
# import os
# from pathlib import Path
# import app
#
# # 添加项目根目录到Python路径
# project_root = Path(__file__).parent.parent
# sys.path.append(str(project_root))
#
# def test_basic_imports():
#     """测试基础模块导入"""
#     print("Testing basic imports...")
#
#     try:
#         # 测试FastAPI相关
#         import fastapi
#         print("FastAPI imported successfully")
#
#         # 测试数据库相关
#         import aiomysql
#         print("aiomysql imported successfully")
#
#         import motor
#         print("motor (MongoDB) imported successfully")
#
#         # 测试配置
#         from app.config import settings
#         print("App config imported successfully")
#
#         # 测试基础服务
#         from app.services.mysql_service import MySQLService
#         print("MySQL service imported successfully")
#
#         from app.services.mongo_service import MongoService
#         print("MongoDB service imported successfully")
#
#         # 测试路由
#         from app.main import app
#         print("Main app imported successfully")
#
#         return True
#
#     except Exception as e:
#         print(f"Import failed: {e}")
#         return False
#
# def test_config():
#     """测试配置"""
#     print("\nTesting configuration...")
#
#     try:
#         from app.config import settings
#
#         # 检查关键配置
#         configs_to_check = [
#             'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER',
#             'MYSQL_PASSWORD', 'MYSQL_DATABASE',
#             'MONGO_URI', 'MONGO_DB'
#         ]
#
#         missing = []
#         for config in configs_to_check:
#             if not hasattr(settings, config) or not getattr(settings, config):
#                 missing.append(config)
#
#         if missing:
#             print(f"Missing configurations: {', '.join(missing)}")
#             print("Please check your .env file")
#             return False
#
#         print("All required configurations are set")
#         print(f"MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
#         print(f"MongoDB: {settings.MONGO_DB}")
#         return True
#
#     except Exception as e:
#         print(f"Configuration test failed: {e}")
#         return False
#
# def main():
#     """主测试函数"""
#     print("Starting backend basic tests...\n")
#
#     # 执行测试
#     import_ok = test_basic_imports()
#     config_ok = test_config()
#
#     print(f"\n{'='*50}")
#     print("TEST SUMMARY")
#     print(f"{'='*50}")
#     print(f"Import test: {'PASS' if import_ok else 'FAIL'}")
#     print(f"Config test: {'PASS' if config_ok else 'FAIL'}")
#
#     all_passed = import_ok and config_ok
#
#     if all_passed:
#         print("\nAll basic tests PASSED!")
#         print("Backend is ready for API server startup.")
#         print("\nNext steps:")
#         print("1. Run: uvicorn app.main:app --reload")
#         print("2. Visit: http://localhost:8000/docs")
#     else:
#         print("\nSome tests FAILED!")
#         print("Please fix the issues before starting the server.")
#
#     return all_passed
#
# if __name__ == "__main__":
#     success = main()
#     sys.exit(0 if success else 1)