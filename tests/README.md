# 游戏测试案例

本目录包含用于测试文字跑团游戏系统的测试案例。这些测试案例模拟玩家在游戏中可能发生的各种场景和事件，帮助验证系统的各个组件是否按预期工作。

## 测试结构

测试案例按照功能模块划分为以下几个文件：

- `test_room_management.py`: 房间管理相关测试，包括创建房间、加入/离开房间、设置准备状态等
- `test_game_flow.py`: 游戏流程相关测试，包括开始游戏、角色选择、DM回合、玩家回合、骰子检定等
- `test_edge_cases.py`: 边界条件和异常情况测试，包括最小/最大玩家数、玩家断线、无效操作等

此外，还有以下辅助文件：

- `api_client.py`: API客户端，用于与游戏服务器API交互
- `test_helpers.py`: 测试辅助函数，提供常用的测试辅助方法
- `run_tests.py`: 测试运行器，用于运行测试案例

## 测试前提

1. 游戏服务器已启动并正常运行
2. 服务器已注册debug接口，用于测试状态设置和重置
3. 服务器中已创建测试用户（用户名：test_user，密码：password）

## 运行测试

### 在VSCode中运行测试

项目已配置VSCode调试配置，可以直接在VSCode中运行测试：

1. 打开VSCode调试面板（按F5或点击左侧活动栏的"运行和调试"图标）
2. 从下拉菜单中选择以下测试配置之一：
   - **测试: 运行所有测试** - 运行所有测试案例
   - **测试: 房间管理** - 运行房间管理相关测试
   - **测试: 游戏流程** - 运行游戏流程相关测试
   - **测试: 边界条件** - 运行边界条件和异常情况测试
   - **测试: 当前测试文件** - 运行当前打开的测试文件中的所有测试
3. 点击绿色的运行按钮或按F5开始调试

这些配置会在集成终端中运行测试，并允许设置断点进行调试。

### 在命令行中运行测试

也可以在命令行中直接运行测试：

#### 运行所有测试

```bash
python tests/run_tests.py
```

#### 运行特定模块的测试

```bash
python tests/run_tests.py -m test_room_management
```

#### 运行特定类的测试

```bash
python tests/run_tests.py -m test_room_management -c TestRoomManagement
```

#### 运行特定方法的测试

```bash
python tests/run_tests.py -m test_room_management -c TestRoomManagement -f test_create_room
```

#### 运行多个特定测试

```bash
python tests/run_tests.py -t test_room_management.TestRoomManagement.test_create_room test_game_flow.TestGameFlow.test_start_game
```

## 测试案例说明

### 房间管理测试

- `test_create_room`: 测试创建房间功能
- `test_join_leave_room`: 测试加入和离开房间功能
- `test_player_ready`: 测试玩家准备状态设置功能
- `test_max_players`: 测试房间最大玩家数限制
- `test_host_transfer`: 测试房主转移功能

### 游戏流程测试

- `test_start_game`: 测试开始游戏功能
- `test_character_selection`: 测试角色选择功能
- `test_dm_turn`: 测试DM回合功能
- `test_player_action_turn`: 测试玩家行动回合功能
- `test_dice_turn`: 测试骰子检定回合功能
- `test_complete_game_cycle`: 测试完整游戏循环

### 边界条件和异常情况测试

- `test_min_players`: 测试最小玩家数限制
- `test_max_players`: 测试最大玩家数限制
- `test_player_disconnect`: 测试玩家断线情况
- `test_host_disconnect`: 测试房主断线情况
- `test_invalid_action`: 测试无效操作
- `test_inactive_player_action`: 测试非活跃玩家行动
- `test_dice_roll_edge_cases`: 测试骰子检定边界情况

## 添加新测试

要添加新的测试案例，请按照以下步骤操作：

1. 确定测试所属的模块（房间管理、游戏流程或边界条件）
2. 在相应的测试文件中添加新的测试方法
3. 测试方法名称应以`test_`开头，并清晰描述测试内容
4. 使用`self.helpers`提供的辅助方法简化测试代码
5. 使用`self.assert*`方法验证测试结果

示例：

```python
def test_new_feature(self):
    """测试新功能"""
    # 创建测试环境
    room_id, match_id, player_ids = self.helpers.setup_complete_game()
    self.assertIsNotNone(room_id, "创建游戏环境失败")
    
    # 执行测试操作
    result = self.api_client.some_new_api_call(room_id)
    
    # 验证结果
    self.assertIsNotNone(result, "调用API失败")
    self.assertTrue(result.get("success"), "操作未成功")
    # 更多验证...
```

## 调试接口

测试案例依赖于服务器提供的以下debug接口：

- `/api/debug/reset`: 重置游戏状态
- `/api/debug/create_test_room`: 创建测试房间
- `/api/debug/create_test_game`: 创建测试游戏
- `/api/debug/create_test_turn`: 创建测试回合
- `/api/debug/game_state`: 获取完整游戏状态
- `/api/debug/simulate_player_action`: 模拟玩家行动
- `/api/debug/simulate_dm_turn`: 模拟DM回合

这些接口在`web/routes/gm_routes.py`中定义，并在`web/server.py`中注册。
