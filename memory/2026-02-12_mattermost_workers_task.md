# 13个OpenClaw Worker创建Mattermost账号任务

## 背景
老板要求为服务器上剩余的13个openclaw worker创建Mattermost账号，并拉进 #aikernengong 群。

## 当前状态
- 等待exec权限批准以查看服务器上的openclaw实际部署列表
- 需要确认13个worker的具体位置、配置和命名

## 已知信息
### 历史记录（可能已合并为3个）
| 目录 | Bot | 状态 |
|------|-----|------|
| /home/ubuntu/openclaw-bots/ | greeter, legalguard, secguard, taskmaster | 旧4个 |
| /home/ubuntu/.openclaw-xxx/ | 其他9个 | 新9个 |

### 当前工作的3个
| Bot | 合并自 | 端口 | 配置路径 |
|-----|--------|------|----------|
| supporter | greeter + moderator | 18830 | ~/.openclaw-supporter/ |
| secguard | legalguard + skillguard | 18791 | ~/.openclaw-secguard/ |
| opsguard | skilldev + taskmaster | 18820 | ~/.openclaw-opsguard/ |

## 待确认
1. 这13个是实际的独立worker还是指团队成员？
2. 如果是团队成员（13个），是否需要为每个创建OpenClaw profile？
3. Mattermost账号的命名规则：worker1, worker2... 还是角色名？

## 执行计划（待确认后）
1. [ ] 确认13个worker的具体列表
2. [ ] 准备Mattermost账号批量创建脚本
3. [ ] 为每个worker获取OpenClaw token
4. [ ] 批量创建Mattermost账号
5. [ ] 拉进#aikernengong频道
6. [ ] 验证连接

## Mattermost管理信息
- 服务器: http://49.232.155.69:8065
- 管理员: 2499510083@qq.com / asd8841315..
- Team ID: xae6dbfbypgsdritgbxwedjszc
