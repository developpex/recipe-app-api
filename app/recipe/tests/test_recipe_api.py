"""
Tests for recipe APIs
"""
import tempfile
import os

from PIL import Image

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Recipe,
    Tag,
    Ingredient
)

from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailSerializer,
)

RECIPES_URL = reverse("recipe:recipe-list")


def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)


def detail_url(recipe_id):
    """Create and return a recipe detail URL."""
    return reverse("recipe:recipe-detail", args=[recipe_id])


def image_upload_url(recipe_id):
    """Create and return an image upload URL."""
    return reverse("recipe:recipe-upload-image", args=[recipe_id])


def create_recipe(user, **params):
    """Create and return a sample recipe."""
    defaults = {
        "title": "Sample recipe title",
        "time_minutes": 22,
        "price": Decimal("5.25"),
        "description": "Sample recipe description",
        "link": "http://example.com/recipe.pdf"
    }
    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


class PublicRecipeAPITests(TestCase):
    """Test unauthenticated API request."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Test authenticated API request."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="user@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_recipe(self):
        """Test retrieving a list of recipes."""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        recipes = Recipe.objects.all().order_by("-id")
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is limited to authenticated user."""
        new_user = create_user(
            email="newuser@example.com",
            password="testpass123"
        )

        create_recipe(user=new_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """Test get recipe detail."""
        recipe = create_recipe(self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe."""
        payload = {
            "title": "Sample recipe",
            "time_minutes": 30,
            "price": Decimal("5.99"),
            "link": "https://example.com/recipe.pdf"
        }
        res = self.client.post(RECIPES_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=res.data["id"])
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        """Test partial update of a recipe."""
        original_link = "https://example.com/recipe.pdf"
        recipe = create_recipe(
            user=self.user,
            title="Sample recipe title",
            link=original_link,
        )

        payload = {"title": "New recipe title"}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload["title"])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        """Test full update of recipe."""
        recipe = create_recipe(
            user=self.user,
            title="Sample recipe title",
            link="https://exmaple.com/recipe.pdf",
            description="Sample recipe description.",
        )

        payload = {
            "title": "New recipe title",
            "link": "https://example.com/new-recipe.pdf",
            "description": "New recipe description",
            "time_minutes": 10,
            "price": Decimal("2.50"),
        }
        url = detail_url(recipe.id)
        res = self.client.put(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        recipe.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_update_user_returns_error(self):
        """Test changing the recipe user results in an error."""
        new_user = create_user(email="user2@example.com", password="test123")
        recipe = create_recipe(user=self.user)

        payload = {"user": new_user.id}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Test deleting a recipe successful."""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_recipe_other_users_recipe_error(self):
        """Test trying to delete another users recipe gives error."""
        new_user = create_user(email="user2@example.com", password="test123")
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with new tags."""
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 10,
            "price": Decimal("2.50"),
            "link": "https://example.com/new-recipe.pdf",
            "tags": [
                {"name": "Thai"},
                {"name": "Dinner"}
            ]
        }

        res = self.client.post(RECIPES_URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)

        for tag in payload["tags"]:
            tag_exist = recipe.tags.filter(
                name=tag["name"],
                user=self.user
            ).exists()
            self.assertTrue(tag_exist)

    def test_create_recipe_with_existing_tags(self):
        """Test creating a recipe with existing tag."""
        thai_tag = Tag.objects.create(user=self.user, name="Thai")
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 10,
            "price": Decimal("2.50"),
            "link": "https://example.com/new-recipe.pdf",
            "tags": [
                {"name": "Thai"},
                {"name": "Dinner"}
            ]
        }

        res = self.client.post(RECIPES_URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(thai_tag, recipe.tags.all())

        for tag in payload["tags"]:
            tag_exist = recipe.tags.filter(
                name=tag["name"],
                user=self.user
            ).exists()
            self.assertTrue(tag_exist)

    def test_create_tag_on_update(self):
        """Create a new tag when update a recipe"""
        recipe = create_recipe(user=self.user)
        payload = {
            "tags": [{"name": "Thai"}]
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        new_tag = Tag.objects.get(user=self.user, name="Thai")
        self.assertIn(new_tag, recipe.tags.all())

    def test_get_existing_tag_on_update(self):
        """Get an existing tag when update a recipe"""
        tag = Tag.objects.create(user=self.user, name="Vietnamese")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        new_tag = Tag.objects.create(user=self.user, name="Thai")
        payload = {
            "tags": [{"name": "Thai"}]
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertIn(new_tag, recipe.tags.all())
        self.assertNotIn(tag, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clearing a recipes tag"""
        tag = Tag.objects.create(user=self.user, name="Vietnamese")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {
            "tags": []
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """Test creating a recipe with new ingredients."""
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 10,
            "price": Decimal("2.50"),
            "link": "https://example.com/new-recipe.pdf",
            "tags": [
                {"name": "Thai"},
                {"name": "Dinner"}
            ],
            "ingredients": [
                {"name": "Prawn"},
                {"name": "Curry"}
            ]
        }

        res = self.client.post(RECIPES_URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)

        for ingredient in payload["ingredients"]:
            ingredient_exist = recipe.ingredients.filter(
                name=ingredient["name"],
                user=self.user
            ).exists()
            self.assertTrue(ingredient_exist)

    def test_create_recipe_with_existing_ingredients(self):
        """Test creating a recipe with existing ingredient."""
        prawn_ingredient = Ingredient.objects.create(
            user=self.user,
            name="Prawn"
        )
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 10,
            "price": Decimal("2.50"),
            "link": "https://example.com/new-recipe.pdf",
            "tags": [
                {"name": "Thai"},
                {"name": "Dinner"}
            ],
            "ingredients": [
                {"name": "Prawn"},
                {"name": "Noodles"}
            ]
        }

        res = self.client.post(RECIPES_URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(prawn_ingredient, recipe.ingredients.all())

        for ingredient in payload["ingredients"]:
            ingredient_exist = recipe.ingredients.filter(
                name=ingredient["name"],
                user=self.user
            ).exists()
            self.assertTrue(ingredient_exist)

    def test_create_ingredient_on_update(self):
        """Create a new ingredient when update a recipe"""
        recipe = create_recipe(user=self.user)
        payload = {
            "ingredients": [{"name": "Bread"}]
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        new_ingredient = Ingredient.objects.get(user=self.user, name="Bread")
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_get_existing_ingredient_on_update(self):
        """Get an existing ingredient when update a recipe"""
        ingredient = Ingredient.objects.create(
            user=self.user,
            name="Milk"
        )
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        new_ingredient = Ingredient.objects.create(
            user=self.user,
            name="Bread"
        )
        payload = {
            "ingredients": [{"name": "Bread"}]
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertIn(new_ingredient, recipe.ingredients.all())
        self.assertNotIn(ingredient, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        """Test clearing a recipes tag"""
        ingredient = Ingredient.objects.create(user=self.user, name="Milk")
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {
            "ingredients": []
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(recipe.ingredients.count(), 0)


class ImageUploadTest(TestCase):
    """Tests for the image upload API."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="user@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete(0)

    def test_upload_image(self):
        """Test uploading image to a recipe."""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            img = Image.new("RGB", (10, 10))
            img.save(image_file, format="JPEG")
            # go to beginning of the file, pointer is on te end after uploading
            image_file.seek(0)
            payload = {
                "image": image_file
            }
            res = self.client.post(url, payload, format="multipart")

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading invalid image"""
        url = image_upload_url(self.recipe.id)
        payload = {
            "image": "not an image"
        }

        res = self.client.post(url, payload, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
