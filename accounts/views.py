from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.conf import settings
from django.db.models import Q
import os
from datetime import datetime
from .models import User, Product, Interaction, Order, Comment
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer, 
    UserUpdateSerializer, ProductSerializer, InteractionSerializer, OrderSerializer, CommentSerializer, CommentTreeSerializer, OrderDetailSerializer
)
from rest_framework import serializers

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

class LoginView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        # 更新登录时间
        user.login_at = timezone.now()
        user.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })

class UserInfoView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

class UpdateUserView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserUpdateSerializer
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class UploadProfilePictureView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if 'profile_picture' not in request.FILES:
            return Response(
                {'error': '请选择要上传的图片文件'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        # 删除旧的头像文件（如果存在）
        if user.profile_picture:
            user.profile_picture.delete(save=False)
            
        # 保存新的头像文件
        user.profile_picture = request.FILES['profile_picture']
        user.save()
        
        return Response({
            'message': '头像上传成功',
            'profile_picture': request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None
        })

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        # 验证必填字段
        if not all([old_password, new_password, confirm_password]):
            return Response(
                {'error': '请提供所有必需的密码字段'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证旧密码
        if not user.check_password(old_password):
            return Response(
                {'error': '旧密码不正确'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证新密码和确认密码是否匹配
        if new_password != confirm_password:
            return Response(
                {'error': '新密码和确认密码不匹配'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证新密码长度
        if len(new_password) < 8:
            return Response(
                {'error': '新密码长度不能少于8个字符'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新密码
        user.set_password(new_password)
        user.save()

        # 更新session认证，防止用户被登出
        update_session_auth_hash(request, user)

        return Response({
            'message': '密码修改成功'
        })

class CreateProductView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # 处理cover_list字段，确保它是字符串格式
        if 'cover_list' in request.data and isinstance(request.data['cover_list'], list):
            request.data['cover_list'] = ','.join(request.data['cover_list'])
            
        return super().create(request, *args, **kwargs)

class ListUserProductsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(user=self.request.user)

class ProductCategoriesView(APIView):
    """获取商品分类列表"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        categories = [
            {'id': id, 'name': name}
            for id, name in Product.CATEGORY_CHOICES
        ]
        return Response(categories)

class UploadProductImageView(APIView):
    """商品图片上传接口 - 支持多图上传"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if 'images[]' not in request.FILES:
            return Response(
                {'error': '请选择要上传的图片文件'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取所有上传的图片
        images = request.FILES.getlist('images[]')
        
        # 验证图片数量
        if len(images) > 10:
            return Response(
                {'error': '一次最多只能上传10张图片'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 允许的文件类型
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        # 存储上传成功的图片URL
        uploaded_urls = []
        # 存储上传失败的图片信息
        failed_uploads = []

        for image in images:
            try:
                # 验证文件类型
                if image.content_type not in allowed_types:
                    failed_uploads.append({
                        'name': image.name,
                        'error': '不支持的图片格式。支持的格式：JPG, PNG, GIF, WEBP'
                    })
                    continue
                    
                # 验证文件大小（限制为5MB）
                if image.size > 5 * 1024 * 1024:
                    failed_uploads.append({
                        'name': image.name,
                        'error': '图片大小不能超过5MB'
                    })
                    continue

                # 生成文件保存路径
                current_date = datetime.now().strftime('%Y%m%d')
                filename = f"{current_date}_{image.name}"
                relative_path = os.path.join('products', str(request.user.id), filename)
                
                # 确保目录存在
                full_path = os.path.join(settings.MEDIA_ROOT, 'products', str(request.user.id))
                os.makedirs(full_path, exist_ok=True)
                
                # 保存文件
                full_file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                with open(full_file_path, 'wb+') as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)
                        
                # 生成访问URL并添加到成功列表
                image_url = request.build_absolute_uri(settings.MEDIA_URL + relative_path)
                uploaded_urls.append(image_url)

            except Exception as e:
                failed_uploads.append({
                    'name': image.name,
                    'error': str(e)
                })

        # 构建响应数据
        response_data = {
            'message': f'成功上传 {len(uploaded_urls)} 张图片' + 
                      (f'，{len(failed_uploads)} 张上传失败' if failed_uploads else ''),
            'urls': uploaded_urls,
        }
        
        # 如果有上传失败的图片，添加到响应中
        if failed_uploads:
            response_data['failed'] = failed_uploads

        # 如果所有图片都上传失败，返回400状态码
        if not uploaded_urls and failed_uploads:
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(response_data)

class ListAllProductsView(generics.ListAPIView):
    """获取所有用户发布的商品列表，支持搜索和过滤"""
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    
    def get_queryset(self):
        queryset = Product.objects.all().order_by('-create_at')
        
        # 搜索商品名称
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
            
        # 按分类过滤
        category = self.request.query_params.get('category', None)
        if category and category.isdigit():
            queryset = queryset.filter(category_id=int(category))
            
        # 按价格范围过滤
        min_price = self.request.query_params.get('min_price', None)
        max_price = self.request.query_params.get('max_price', None)
        if min_price and min_price.replace('.', '').isdigit():
            queryset = queryset.filter(price__gte=float(min_price))
        if max_price and max_price.replace('.', '').isdigit():
            queryset = queryset.filter(price__lte=float(max_price))
            
        # 按是否可议价过滤
        is_bargain = self.request.query_params.get('is_bargain', None)
        if is_bargain is not None:
            is_bargain = is_bargain.lower() == 'true'
            queryset = queryset.filter(is_bargain=is_bargain)
            
        # 按新旧程度过滤
        min_old_level = self.request.query_params.get('min_old_level', None)
        max_old_level = self.request.query_params.get('max_old_level', None)
        if min_old_level and min_old_level.isdigit():
            queryset = queryset.filter(old_level__gte=int(min_old_level))
        if max_old_level and max_old_level.isdigit():
            queryset = queryset.filter(old_level__lte=int(max_old_level))
            
        return queryset

class UserDetailView(generics.RetrieveAPIView):
    """根据用户ID获取用户信息"""
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = 'id'

class ProductDetailView(generics.RetrieveAPIView):
    """根据商品ID获取商品详细信息"""
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    lookup_field = 'id'

class UpdateProductView(generics.UpdateAPIView):
    """更新商品信息"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    lookup_field = 'id'
    
    def get_queryset(self):
        """只允许用户更新自己的商品"""
        return Product.objects.filter(user=self.request.user)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # 处理cover_list字段，确保它是字符串格式
        if 'cover_list' in request.data and isinstance(request.data['cover_list'], list):
            request.data['cover_list'] = ','.join(request.data['cover_list'])
            
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class DeleteProductView(generics.DestroyAPIView):
    """删除商品"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    lookup_field = 'id'
    
    def get_queryset(self):
        """只允许用户删除自己的商品"""
        return Product.objects.filter(user=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': '商品已成功删除'
        }, status=status.HTTP_200_OK)

class InteractionCreateView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = (JSONParser,)

    def post(self, request, *args, **kwargs):
        serializer = InteractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class WantProductListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        interactions = Interaction.objects.filter(user=request.user, type=3)
        product_ids = interactions.values_list('product_id', flat=True)
        products = Product.objects.filter(id__in=product_ids)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

class ProductInteractionStatView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': '缺少product_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        want_count = Interaction.objects.filter(product_id=product_id, type=3).count()
        browse_count = Interaction.objects.filter(product_id=product_id, type=1).count()
        favorite_count = Interaction.objects.filter(product_id=product_id, type=2).count()
        return Response({
            'product_id': int(product_id),
            'want_count': want_count,
            'browse_count': browse_count,
            'favorite_count': favorite_count
        })

class FavoriteProductListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        interactions = Interaction.objects.filter(user=request.user, type=2)
        product_ids = interactions.values_list('product_id', flat=True)
        products = Product.objects.filter(id__in=product_ids)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

class BrowsedProductListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        interactions = Interaction.objects.filter(user=request.user, type=1)  # type=1 表示浏览
        product_ids = interactions.values_list('product_id', flat=True)
        products = Product.objects.filter(id__in=product_ids)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

class UnfavoriteProductView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': '缺少product_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            interaction = Interaction.objects.get(user=request.user, product_id=product_id, type=2)
            interaction.delete()
            return Response({'message': '已取消收藏'}, status=status.HTTP_200_OK)
        except Interaction.DoesNotExist:
            return Response({'error': '未找到收藏记录'}, status=status.HTTP_404_NOT_FOUND)

class IsFavoriteProductView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': '缺少product_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        is_favorite = Interaction.objects.filter(user=request.user, product_id=product_id, type=2).exists()
        return Response({'is_favorite': is_favorite})

class OrderCreateView(generics.CreateAPIView):
    """创建订单视图"""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def create(self, request, *args, **kwargs):
        # 验证商品ID
        product_id = request.data.get('product')
        if not product_id:
            return Response(
                {'product': '必须提供商品ID'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'product': '商品不存在'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError:
            return Response(
                {'product': '商品ID必须是有效的整数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证购买价格
        buy_price = request.data.get('buy_price')
        if not buy_price:
            return Response(
                {'buy_price': '必须提供购买价格'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            buy_price = float(buy_price)
            if buy_price <= 0:
                raise ValueError
        except ValueError:
            return Response(
                {'buy_price': '购买价格必须是大于0的数字'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证交易状态
        trade_status = request.data.get('trade_status')
        if trade_status is None:
            return Response(
                {'trade_status': '必须提供交易状态'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            trade_status = int(trade_status)
            if trade_status not in dict(Order.TRADE_STATUS_CHOICES):
                raise ValueError
        except ValueError:
            return Response(
                {'trade_status': f'无效的交易状态。有效的状态为: {dict(Order.TRADE_STATUS_CHOICES)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证商品库存
        if product.inventory is not None and product.inventory <= 0:
            return Response(
                {'product': '商品库存不足'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证不能购买自己的商品
        if product.user == request.user:
            return Response(
                {'product': '不能购买自己的商品'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 创建订单数据
        order_data = request.data.copy()
        order_data['buyer'] = request.user.id  # 设置买家为当前用户

        # 创建订单
        serializer = self.get_serializer(data=order_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # 更新商品库存
        if product.inventory is not None:
            product.inventory -= 1
            product.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class CommentView(generics.ListCreateAPIView):
    """商品评论视图：支持创建评论和获取评论列表"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = CommentSerializer
    queryset = Comment.objects.all()
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_serializer_class(self):
        """根据请求方法返回不同的序列化器"""
        if self.request.method == 'GET':
            return CommentTreeSerializer
        return CommentSerializer

    def get_queryset(self):
        """获取评论列表"""
        # 从请求体中获取product_id
        product_id = self.request.data.get('product_id')
        
        if not product_id:
            raise serializers.ValidationError({
                'product_id': '必须提供商品ID'
            })
        
        # 验证商品是否存在
        try:
            Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError({
                'product_id': '商品不存在'
            })
        except ValueError:
            raise serializers.ValidationError({
                'product_id': '商品ID必须是有效的整数'
            })
        
        # 只获取一级评论（parent为null的评论）
        return Comment.objects.filter(
            product_id=product_id,
            parent__isnull=True
        ).order_by('-create_time')

    def list(self, request, *args, **kwargs):
        """重写list方法以处理验证错误"""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        """创建评论"""
        # 创建请求数据的可变副本
        data = request.data.copy()
        # 设置用户ID
        data['user_id'] = request.user.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class BuyOrderListView(generics.ListAPIView):
    """获取用户购买的订单列表"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        """获取当前用户作为买家的所有订单"""
        return Order.objects.filter(
            buyer=self.request.user  # 通过买家字段关联到当前用户
        ).select_related('product', 'product__user').order_by('-create_time')

class SellOrderListView(generics.ListAPIView):
    """获取用户卖出的订单列表"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        """获取当前用户作为卖家的所有订单"""
        return Order.objects.filter(
            product__user=self.request.user  # 通过商品关联到卖家
        ).select_related('product', 'product__user', 'buyer').order_by('-create_time')

class ReviewOrderView(APIView):
    """审核订单视图"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def post(self, request):
        # 获取订单编号
        order_id = request.data.get('order_id')
        if not order_id:
            return Response(
                {'error': '必须提供订单编号'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order_id = int(order_id)
        except ValueError:
            return Response(
                {'error': '订单编号必须是有效的整数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取订单
        try:
            order = Order.objects.select_related('product').get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {'error': '订单不存在'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 验证是否是自己的商品订单
        if order.product.user != request.user:
            return Response(
                {'error': '无权审核此订单'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 验证订单状态是否为待交易
        if order.trade_status != Order.TRADE_STATUS_PENDING:
            return Response(
                {'error': '只能审核待交易的订单'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取审核结果
        is_approved = request.data.get('is_approved')
        if is_approved is None:
            return Response(
                {'error': '必须提供审核结果'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            is_approved = bool(is_approved)
        except ValueError:
            return Response(
                {'error': '审核结果必须是布尔值'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新订单状态
        if is_approved:
            order.trade_status = Order.TRADE_STATUS_SUCCESS
            # 交易成功，更新商品库存
            if order.product.inventory is not None:
                order.product.inventory -= 1
                order.product.save()
        else:
            order.trade_status = Order.TRADE_STATUS_FAILED
            # 交易失败，恢复商品库存
            if order.product.inventory is not None:
                order.product.inventory += 1
                order.product.save()

        order.save()

        # 返回更新后的订单信息
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)

class RefundOrderView(APIView):
    """申请退款视图"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def post(self, request):
        # 获取订单编号
        order_id = request.data.get('order_id')
        if not order_id:
            return Response(
                {'error': '必须提供订单编号'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order_id = int(order_id)
        except ValueError:
            return Response(
                {'error': '订单编号必须是有效的整数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取订单
        try:
            order = Order.objects.select_related('product').get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {'error': '订单不存在'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 验证是否是自己的订单
        if order.buyer != request.user:
            return Response(
                {'error': '无权对此订单申请退款'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 验证订单状态是否为交易成功
        if order.trade_status != Order.TRADE_STATUS_SUCCESS:
            return Response(
                {'error': '只能对交易成功的订单申请退款'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新订单状态为退款中
        order.trade_status = Order.TRADE_STATUS_REFUND
        order.save()

        # 返回更新后的订单信息
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)

class ReviewRefundView(APIView):
    """退款审核视图"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def post(self, request):
        # 获取订单编号
        order_id = request.data.get('order_id')
        if not order_id:
            return Response(
                {'error': '必须提供订单编号'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order_id = int(order_id)
        except ValueError:
            return Response(
                {'error': '订单编号必须是有效的整数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取订单
        try:
            order = Order.objects.select_related('product').get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {'error': '订单不存在'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 验证是否是自己的商品订单
        if order.product.user != request.user:
            return Response(
                {'error': '无权审核此订单的退款申请'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 验证订单状态是否为退款中
        if order.trade_status != Order.TRADE_STATUS_REFUND:
            return Response(
                {'error': '只能审核退款中的订单'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取审核结果
        is_approved = request.data.get('is_approved')
        if is_approved is None:
            return Response(
                {'error': '必须提供审核结果'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            is_approved = bool(is_approved)
        except ValueError:
            return Response(
                {'error': '审核结果必须是布尔值'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新订单状态
        if is_approved:
            order.trade_status = Order.TRADE_STATUS_REVIEW  # 退款成功
            # 退款成功，恢复商品库存
            if order.product.inventory is not None:
                order.product.inventory += 1
                order.product.save()
        else:
            order.trade_status = Order.TRADE_STATUS_SUCCESS  # 退回交易成功状态

        order.save()

        # 返回更新后的订单信息
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)