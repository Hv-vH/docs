"""
Postman API测试用例

1. 用户注册接口测试
POST /api/register/
{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
}
预期响应:
200 OK
{
    "username": "testuser",
    "email": "test@example.com"
}

2. 用户登录接口测试
POST /api/login/
{
    "username": "testuser",
    "password": "password123"
}
预期响应:
200 OK
{
    "token": "生成的Token值",
    "user": {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "created_at": "创建时间",
        "login_at": "登录时间",
        "profile_picture": null
    }
}

3. 获取用户信息接口测试
GET /api/user/
Headers:
Authorization: Token 生成的Token值
预期响应:
200 OK
{
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "created_at": "创建时间",
    "login_at": "登录时间",
    "profile_picture": null
}

4. 更新用户信息接口测试
PATCH /api/user/update/
Headers:
Authorization: Token 生成的Token值
{
    "email": "updated@example.com",
    "profile_picture": "上传的图片文件"
}
预期响应:
200 OK
{
    "username": "testuser",
    "email": "updated@example.com",
    "profile_picture": "图片URL"
}

5. 登录失败测试 - 错误密码
POST /api/login/
{
    "username": "testuser",
    "password": "wrongpassword"
}
预期响应:
400 Bad Request
{
    "non_field_errors": [
        "用户名或密码不正确"
    ]
}

6. 注册失败测试 - 已存在用户名
POST /api/register/
{
    "username": "testuser",
    "email": "another@example.com",
    "password": "password123"
}
预期响应:
400 Bad Request
{
    "username": [
        "该用户名已经存在"
    ]
}

7. 获取用户信息失败测试 - 无效Token
GET /api/user/
Headers:
Authorization: Token 无效Token值
预期响应:
401 Unauthorized
{
    "detail": "无效令牌"
}

8. 上传头像图片接口
POST /api/user/upload-avatar/
请求头:
Authorization: Token your_token_here
Content-Type: multipart/form-data
请求体:
profile_picture: 图片文件

9. 修改密码接口
URL: /api/user/change-password/
方法: POST
请求头:
Authorization: Token your_token_here
Content-Type: application/json
 {
       "old_password": "当前密码",
       "new_password": "新密码",
       "confirm_password": "确认新密码"
   }

10.# 基础获取所有商品
GET /api/products/

11.# 搜索名称包含"手机"的商品
GET /api/products/?search=手机

12.# 获取分类ID为1且价格在100-1000之间的商品
GET /api/products/?category=1&min_price=100&max_price=1000

13# 获取可议价且新旧程度在7-10之间的商品
GET /api/products/?is_bargain=true&min_old_level=7&max_old_level=10

14. 编辑商品接口
URL: /api/products/{id}/update/
方法: PATCH 或 PUT
描述: 更新指定ID的商品信息
权限: 仅允许已登录用户编辑自己的商品
请求头:
Authorization: Token your_token_here
Content-Type: application/json

15.删除商品接口
URL: /api/products/{id}/delete/
方法: DELETE
描述: 删除指定ID的商品
权限: 仅允许已登录用户删除自己的商品
请求头:
Authorization: Token your_token_here

16. 互动行为接口测试
POST /api/interactions/
{
    "user_id": 1,
    "product_id": 2,
    "type": 2,
    "create_time": "2025-03-25T14:15:00"
}
预期响应:
201 Created
{
    "user_id": 1,
    "product_id": 2,
    "type": 2,
    "create_time": "2025-03-25T14:15:00"
}

17. 获取我想要的商品接口测试
GET /api/interactions/want/
Headers:
Authorization: Token your_token_here
预期响应:
200 OK
[
    {
        "id": 2,
        "name": "商品A",
        "category_id": 1,
        "category_name": "书本",
        "cover_list": "...",
        "detail": "...",
        "inventory": 10,
        "is_bargain": false,
        "old_level": 9,
        "price": 100.0,
        "user_id": 1,
        "create_at": "2025-03-25T14:15:00"
    },
    ...
]

异常场景：
- 缺少必填字段，预期 400 Bad Request
- type 非法，预期 400 Bad Request

18. 创建订单接口测试
POST /accounts/orders/create/
Headers:
Authorization: Token your_token_here
Content-Type: application/json
请求体示例：
Apply to tests.py
{
    "detail": "买家留言：请尽快发货",
    "product": 1,
    "buy_price": 99.99,
    "trade_status": 0
}
预期响应:
201 Created
Apply to tests.py
{
    "id": 5,
    "code": "ORD17172345671234",
    "detail": "买家留言：请尽快发货",
    "product": 1,
    "buy_price": "99.99",
    "trade_status": 0,
    "trade_time": "2024-06-01T12:00:00Z",
    "create_time": "2024-06-01T12:00:00Z"
}
字段说明：
code：订单号，后端自动生成
trade_time：交易时间，后端自动生成
create_time：创建时间，后端自动生成
其它字段见请求体
异常场景：
缺少必填字段（如 product、buy_price），预期 400 Bad Request
product 不存在，预期 400 Bad Request
buy_price 非法，预期 400 Bad Request

"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import User, Interaction, Product

class AccountsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.user_info_url = reverse('user-info')
        self.user_update_url = reverse('user-update')
        
        # 创建测试用户数据
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123'
        }
        
    def test_user_registration(self):
        """测试用户注册功能"""
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testuser')
        
    def test_user_login(self):
        """测试用户登录功能"""
        # 先注册用户
        self.client.post(self.register_url, self.user_data, format='json')
        
        # 测试登录
        login_data = {
            'username': 'testuser',
            'password': 'password123'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('token' in response.data)
        self.assertTrue('user' in response.data)
        
    def test_get_user_info(self):
        """测试获取用户信息功能"""
        # 先注册用户
        self.client.post(self.register_url, self.user_data, format='json')
        
        # 登录获取token
        login_data = {
            'username': 'testuser',
            'password': 'password123'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        token = response.data['token']
        
        # 使用token获取用户信息
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get(self.user_info_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        
    def test_update_user_info(self):
        """测试更新用户信息功能"""
        # 先注册用户
        self.client.post(self.register_url, self.user_data, format='json')
        
        # 登录获取token
        login_data = {
            'username': 'testuser',
            'password': 'password123'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        token = response.data['token']
        
        # 更新用户信息
        update_data = {
            'email': 'updated@example.com'
        }
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.patch(self.user_update_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'updated@example.com')
        
    def test_login_invalid_credentials(self):
        """测试使用无效凭据登录"""
        # 先注册用户
        self.client.post(self.register_url, self.user_data, format='json')
        
        # 使用错误密码登录
        login_data = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_register_duplicate_username(self):
        """测试注册重复用户名"""
        # 先注册一个用户
        self.client.post(self.register_url, self.user_data, format='json')
        
        # 使用相同用户名再次注册
        duplicate_data = {
            'username': 'testuser',
            'email': 'another@example.com',
            'password': 'password123'
        }
        response = self.client.post(self.register_url, duplicate_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_unauthorized_access(self):
        """测试未授权访问"""
        response = self.client.get(self.user_info_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_interaction(self):
        """测试用户对商品进行互动行为（浏览/收藏/想要）"""
        # 创建用户和商品
        user = User.objects.create_user(username='user1', email='user1@example.com', password='pass123456')
        product = Product.objects.create(name='测试商品', user=user)
        url = reverse('interaction-create')
        data = {
            'user_id': user.id,
            'product_id': product.id,
            'type': 2,  # 收藏
            'create_time': '2025-03-25T14:15:00'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Interaction.objects.count(), 1)
        interaction = Interaction.objects.first()
        self.assertEqual(interaction.user, user)
        self.assertEqual(interaction.product, product)
        self.assertEqual(interaction.type, 2)

    def test_create_interaction_missing_field(self):
        """测试缺少必填字段时的错误"""
        user = User.objects.create_user(username='user2', email='user2@example.com', password='pass123456')
        product = Product.objects.create(name='测试商品2', user=user)
        url = reverse('interaction-create')
        data = {
            'user_id': user.id,
            # 'product_id' 缺失
            'type': 1,
            'create_time': '2025-03-25T14:15:00'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)

    def test_create_interaction_invalid_type(self):
        """测试无效type类型"""
        user = User.objects.create_user(username='user3', email='user3@example.com', password='pass123456')
        product = Product.objects.create(name='测试商品3', user=user)
        url = reverse('interaction-create')
        data = {
            'user_id': user.id,
            'product_id': product.id,
            'type': 99,  # 非法类型
            'create_time': '2025-03-25T14:15:00'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
