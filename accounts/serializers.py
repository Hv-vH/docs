from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Product, Interaction, Order
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