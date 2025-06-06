from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
import time, random
from django.utils import timezone

class User(AbstractUser):
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    email = models.EmailField(unique=True, null=True)
    login_at = models.DateTimeField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    # 添加related_name解决冲突
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='accounts_user_set',
        related_query_name='accounts_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='accounts_user_set',
        related_query_name='accounts_user'
    )

class Product(models.Model):
    # 商品分类常量
    CATEGORY_BOOK = 1
    CATEGORY_PHONE = 2
    CATEGORY_CLOTHING = 3
    CATEGORY_OTHER = 4

    CATEGORY_CHOICES = [
        (CATEGORY_BOOK, '书本'),
        (CATEGORY_PHONE, '手机'),
        (CATEGORY_CLOTHING, '衣服'),
        (CATEGORY_OTHER, '其他'),
    ]

    name = models.CharField(max_length=200, null=True, verbose_name='商品名')
    category_id = models.IntegerField(
        choices=CATEGORY_CHOICES,
        null=True,
        verbose_name='商品分类id'
    )
    cover_list = models.TextField(null=True, verbose_name='商品封面列表')
    detail = models.TextField(null=True, verbose_name='商品简介')
    inventory = models.IntegerField(null=True, default=1, verbose_name='库存')
    is_bargain = models.BooleanField(null=True, default=False, verbose_name='是否支持砍价')
    old_level = models.IntegerField(null=True, verbose_name='新旧程度')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name='价格')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products', verbose_name='发布者')
    create_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ['-create_at']

    def __str__(self):
        return self.name or '未命名商品'

    def clean(self):
        # 验证分类ID
        if self.category_id and self.category_id not in dict(self.CATEGORY_CHOICES):
            raise ValidationError({
                'category_id': f'无效的分类ID: {self.category_id}'
            })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def category_name(self):
        """获取分类名称"""
        return dict(self.CATEGORY_CHOICES).get(self.category_id, '未知分类')

class Interaction(models.Model):
    TYPE_BROWSE = 1
    TYPE_FAVORITE = 2
    TYPE_WANT = 3
    TYPE_CHOICES = [
        (TYPE_BROWSE, '浏览'),
        (TYPE_FAVORITE, '收藏'),
        (TYPE_WANT, '想要'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interactions', verbose_name='用户')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='interactions', verbose_name='商品')
    type = models.IntegerField(choices=TYPE_CHOICES, verbose_name='互动类型')
    create_time = models.DateTimeField(verbose_name='创建时间')

    class Meta:
        verbose_name = '互动行为'
        verbose_name_plural = '互动行为'
        unique_together = ('user', 'product', 'type', 'create_time')

    def __str__(self):
        return f'{self.user.username} {self.get_type_display()} {self.product.name} @ {self.create_time}'

class Order(models.Model):
    TRADE_STATUS_PENDING = 0
    TRADE_STATUS_SUCCESS = 1
    TRADE_STATUS_FAILED = 2
    TRADE_STATUS_CHOICES = [
        (TRADE_STATUS_PENDING, '待交易'),
        (TRADE_STATUS_SUCCESS, '交易成功'),
        (TRADE_STATUS_FAILED, '交易失败'),
    ]

    code = models.CharField(max_length=255, null=True, unique=True, verbose_name='订单号')
    detail = models.CharField(max_length=255, null=True, verbose_name='备注')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name='商品')
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name='购买时的价格')
    trade_status = models.SmallIntegerField(choices=TRADE_STATUS_CHOICES, null=True, verbose_name='交易状态')
    trade_time = models.DateTimeField(null=True, blank=True, verbose_name='交易时间')
    create_time = models.DateTimeField(auto_now_add=True, null=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '订单'
        verbose_name_plural = '订单'
        ordering = ['-create_time']

    def __str__(self):
        return self.code or f'订单{self.id}'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"ORD{int(time.time())}{random.randint(1000,9999)}"
        if not self.trade_time:
            self.trade_time = timezone.now()
        super().save(*args, **kwargs)