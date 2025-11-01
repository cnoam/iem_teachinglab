# 项目概述

这是一个使用Terraform部署Databricks集群的基础设施即代码项目，专门用于为学生分组分配计算资源。该项目允许将学生分成小组（通常3-4人），每组分配一个独立的Databricks集群。

## 项目架构

该项目主要由以下组件构成：

1. **Terraform配置文件** - 位于`/dbr/`目录下，用于定义和管理Databricks资源
2. **Python脚本** - 用于转换Moodle导出的CSV格式到Terraform可用的格式
3. **实用脚本** - 用于环境变量设置和状态管理

## 核心功能

- **集群创建** - 为每个学生组创建独立的Databricks集群
- **用户管理** - 从CSV文件读取用户邮箱并创建Databricks用户
- **组管理** - 创建学生组并将用户分配到相应组
- **权限设置** - 为每个组分配其对应集群的访问权限
- **库安装** - 在集群上安装所需的Python和Maven库
- **自动关机** - 集群在一定时间后自动终止以节省成本

## 关键文件说明

### Terraform配置文件
- `main.tf` - 主配置文件，定义提供商和数据源
- `variables.tf` - 定义所有可配置变量
- `create_clusters.tf` - 定义集群创建逻辑
- `create_objects.tf` - 定义用户和组创建
- `assign_groups.tf` - 定义组分配和权限设置
- `install_libs.tf` - 定义库安装配置
- `terraform.tfvars` - 存储环境特定的变量值

### 实用脚本
- `convert_moodle_to_tf_format.py` - 将Moodle导出的CSV文件转换为Terraform可用格式
- `create_vars.sh` - 设置必要的环境变量

## 使用方法

### 环境准备
1. 安装Terraform、Databricks CLI和Azure CLI
2. 使用`az login`登录到正确的Azure订阅
3. 运行`terraform init`初始化

### 部署流程
1. 从Moodle下载包含学生邮箱的CSV文件
2. 使用Python脚本转换格式：`python ../convert_moodle_to_tf_format.py path/to/csv/file`
3. 设置环境变量：`source ../create_vars.sh`
4. 执行部署：`terraform apply --parallelism=50`

### 环境变量
- `TF_VAR_databricks_token` - Databricks工作区的访问令牌
- `TF_VAR_databricks_host` - Databricks工作区的主机URL
- `TF_CLI_ARGS_apply` - 应用阶段的并行度设置

## 配置选项

项目支持以下可配置参数：
- `spark_version` - Spark运行时版本（默认: "15.4.x-cpu-ml-scala2.12"）
- `min_workers`/`max_workers` - 集群工作节点数量（默认: 1/6）
- `autotermination_minutes` - 自动终止时间（默认: 20分钟）
- `maven_packages` - Maven库配置（默认: spark-nlp）
- `python_packages` - Python库配置（默认: ["spark-nlp", "nltk"]）

## 开发约定

- 使用Terraform工作区来隔离不同的部署环境
- 推荐使用较高的并行度（如50）以加快部署速度
- 通过修改CSV文件或terraform.tfvars文件可以轻松修改用户、组或集群配置
- 部署分为两个阶段：首先创建集群/用户/组，然后安装库并设置自动关机

## 故障排除

- 如果遇到认证问题，尝试重新运行`terraform init`
- 对于状态锁定问题，可使用`terraform force-unlock`命令
- 对于集群启动超时问题，可能需要手动启动集群后再运行库安装步骤

## 安全注意事项

- 访问令牌等敏感信息被标记为敏感变量，不在输出中显示
- 建议使用短期令牌以增强安全性
- 环境变量文件（如create_vars.sh）应妥善保护，不应提交到版本控制系统