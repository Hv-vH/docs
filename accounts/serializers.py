from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Product, Interaction, Order, Comment
from datetime import datetime

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'created_at', 'login_at', 'profile_picture']
        read_only_fields = ['id', 'created_at', 'login_at']

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError("用户名或密码不正确")

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'profile_picture']
        read_only_fields = ['id', 'created_at', 'login_at']

class ProductSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    category_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category_id', 'category_name', 'cover_list', 
            'detail', 'inventory', 'is_bargain', 'old_level', 
            'price', 'user_id', 'create_at'
        ]
        read_only_fields = ['id', 'create_at', 'user_id', 'category_name']

    def validate_category_id(self, value):
        """验证分类ID"""
        if value not in dict(Product.CATEGORY_CHOICES):
            raise serializers.ValidationError(f'无效的分类ID: {value}。有效的分类ID为: {dict(Product.CATEGORY_CHOICES).keys()}')
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if representation['price'] is not None:
            representation['price'] = float(representation['price'])
        return representation

class InteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaction
        fields = ['user_id', 'product_id', 'type', 'create_time']

    user_id = serializers.IntegerField(source='user.id')
    product_id = serializers.IntegerField(source='product.id')
    create_time = serializers.DateTimeField(required=False)

    def create(self, validated_data):
        user = User.objects.get(id=validated_data['user']['id'])
        product = Product.objects.get(id=validated_data['product']['id'])
        create_time = validated_data.get('create_time', datetime.now())
        interaction = Interaction.objects.create(
            user=user,
            product=product,
            type=validated_data['type'],
            create_time=create_time
        )
        return interaction

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['code', 'trade_time', 'create_time']

class CommentSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')
    product_id = serializers.IntegerField(source='product.id')
    parent_id = serializers.CharField(source='parent.id', required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Comment
        fields = ['id', 'product_id', 'user_id', 'parent_id', 'content', 'create_time']
        read_only_fields = ['id', 'create_time']

    def validate_parent_id(self, value):
        """验证父级评论ID"""
        if value in [None, '', 'null', 'None']:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("父级评论ID必须是有效的整数")

    def validate(self, data):
        """验证父级评论是否存在"""
        parent_id = data.get('parent', {}).get('id')
        if parent_id is not None:
            try:
                Comment.objects.get(id=parent_id)
            except Comment.DoesNotExist:
                raise serializers.ValidationError({"parent_id": "父级评论不存在"})
        return data

    def create(self, validated_data):
        user = User.objects.get(id=validated_data['user']['id'])
        product = Product.objects.get(id=validated_data['product']['id'])
        parent = None
        if 'parent' in validated_data and validated_data['parent'] and validated_data['parent'].get('id'):
            parent = Comment.objects.get(id=validated_data['parent']['id'])
        
        comment = Comment.objects.create(
            user=user,
            product=product,
            parent=parent,
            content=validated_data['content']
        )
        return comment

class CommentTreeSerializer(serializers.ModelSerializer):
    """用于返回树形结构的评论序列化器"""
    user_id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'user_id', 'username', 'content', 'create_time', 'replies']

    def get_replies(self, obj):
        """获取评论的回复列表"""
        # 只获取直接回复（一级回复）
        replies = Comment.objects.filter(parent=obj).order_by('create_time')
        return CommentTreeSerializer(replies, many=True).data

class CommentListSerializer(serializers.ModelSerializer):
    """用于列表查询的评论序列化器"""
    user_id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    product_id = serializers.IntegerField(source='product.id')
    parent_id = serializers.IntegerField(source='parent.id', required=False, allow_null=True)

    class Meta:
        model = Comment
        fields = ['id', 'product_id', 'user_id', 'username', 'parent_id', 'content', 'create_time']