from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class TimeStampedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
	updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

	class Meta:
		abstract = True


class TrackedModel(TimeStampedModel):
	created_by = models.ForeignKey(
		User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_%(class)s"
	)
	is_active = models.BooleanField(default=True, db_index=True)

	class Meta:
		abstract = True


class Category(TrackedModel):
	name = models.CharField(max_length=100, unique=True, db_index=True)
	description = models.TextField(blank=True)
	main_supplier = models.ForeignKey(
		"Supplier", on_delete=models.SET_NULL, null=True, blank=True, related_name="main_categories"
	)

	class Meta:
		ordering = ["name"]
		indexes = [
			models.Index(fields=["name"]),
		]

	def __str__(self):
		return self.name


class Supplier(TrackedModel):
	company_name = models.CharField(max_length=200, unique=True, db_index=True)
	contact_name = models.CharField(max_length=100, blank=True)
	phone = models.CharField(max_length=20, blank=True)
	email = models.EmailField(blank=True)
	address = models.TextField(blank=True)

	class Meta:
		ordering = ["company_name"]
		indexes = [
			models.Index(fields=["company_name"]),
		]

	def __str__(self):
		return self.company_name


class ProductQuerySet(models.QuerySet):
	def available(self):
		return self.filter(stock_quantity__gt=0, is_active=True)

	def priced_between(self, low: float, high: float):
		return self.filter(price__gte=low, price__lte=high)

	def by_tag(self, tag_name: str):
		return self.filter(tags__name=tag_name)

	def with_rating(self):
		return self.annotate(
			review_count=models.Count("reviews", distinct=True),
			avg_rating=models.Avg("reviews__rating"),
		)


class Product(TrackedModel):
	name = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
	category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
	stock_quantity = models.PositiveIntegerField(default=0, db_index=True)
	suppliers = models.ManyToManyField("Supplier", through="ProductSupplier", related_name="products")

	objects = ProductQuerySet.as_manager()

	class Meta:
		ordering = ["name"]
		constraints = [
			models.UniqueConstraint(fields=["name", "category"], name="uniq_product_in_category"),
		]
		indexes = [
			models.Index(fields=["price"]),
			models.Index(fields=["stock_quantity"]),
		]

	def __str__(self):
		return self.name


class ProductDetail(TimeStampedModel):
	product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="details")
	weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
	dimensions = models.CharField(max_length=50, blank=True)
	manufacturer = models.CharField(max_length=100, blank=True)
	warranty_months = models.PositiveIntegerField(null=True, blank=True)

	def __str__(self):
		return f"Детали: {self.product_id}"


class ProductSupplier(TimeStampedModel):
	product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_suppliers")
	supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="product_suppliers")
	purchase_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
	delivery_days = models.PositiveIntegerField(default=0)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["product", "supplier"], name="uniq_product_supplier"),
		]
		indexes = [
			models.Index(fields=["supplier", "product"]),
		]

	def __str__(self):
		return f"{self.product_id}↔{self.supplier_id}"


class Tag(TimeStampedModel):
	name = models.CharField(max_length=50, unique=True, db_index=True)
	description = models.TextField(blank=True)

	class Meta:
		ordering = ["name"]

	def __str__(self):
		return self.name


class ProductTag(models.Model):
	product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_tags")
	tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="product_tags")

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["product", "tag"], name="uniq_product_tag"),
		]
		indexes = [
			models.Index(fields=["tag"]),
		]

	def __str__(self):
		return f"{self.product_id}#{self.tag_id}"


class Customer(TrackedModel):
	first_name = models.CharField(max_length=100, db_index=True)
	last_name = models.CharField(max_length=100, db_index=True)
	email = models.EmailField(unique=True)
	phone = models.CharField(max_length=20, blank=True)
	registration_date = models.DateTimeField(default=timezone.now, db_index=True)

	class Meta:
		ordering = ["last_name", "first_name"]
		indexes = [
			models.Index(fields=["last_name", "first_name"]),
			models.Index(fields=["registration_date"]),
		]

	def __str__(self):
		return f"{self.last_name} {self.first_name}"


class Order(TrackedModel):
	class Status(models.TextChoices):
		PENDING = "pending", "pending"
		COMPLETED = "completed", "completed"
		SHIPPED = "shipped", "shipped"
		CANCELLED = "cancelled", "cancelled"

	customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
	order_date = models.DateTimeField(default=timezone.now, db_index=True)
	total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

	class Meta:
		ordering = ["-order_date"]
		indexes = [
			models.Index(fields=["status", "order_date"]),
			models.Index(fields=["customer", "order_date"]),
		]

	def __str__(self):
		return f"Order #{self.pk}"


class OrderItem(TimeStampedModel):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
	quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
	unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["order", "product"], name="uniq_order_product"),
		]
		indexes = [
			models.Index(fields=["order"]),
		]

	def __str__(self):
		return f"{self.order_id}:{self.product_id}"


class Review(TimeStampedModel):
	product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
	customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="reviews")
	rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], db_index=True)
	comment = models.TextField(blank=True)

	class Meta:
		indexes = [
			models.Index(fields=["product", "rating"]),
		]

	def __str__(self):
		return f"{self.product_id}@{self.customer_id}:{self.rating}"
