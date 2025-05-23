"""
Test for the ingredients API.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient

from recipe.serializers import IngredientSerializer

INGREDIENT_URL = reverse("recipe:ingredient-list")


def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)


def create_ingredient(user, **params):
    """Create and return a new Ingredient."""
    defaults = {
        "name": "Ingredient Name"
    }
    defaults.update(params)

    ingredient = Ingredient.objects.create(user=user, **defaults)
    return ingredient


def detail_url(ingredient_id):
    """Return a detail url for ingredient"""
    return reverse("recipe:ingredient-detail", args=[ingredient_id])


class PublicIngredientApiTests(TestCase):
    """Test unauthenticated API request."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.get(INGREDIENT_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientApiTest(TestCase):
    """Test authenticated API request."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="user@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self):
        """Test retrieving a list of ingredients"""

        create_ingredient(user=self.user, name="Milk")
        create_ingredient(user=self.user, name="Butter")

        res = self.client.get(INGREDIENT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        ingredients = Ingredient.objects.all().order_by("-name")
        serializer = IngredientSerializer(ingredients, many=True)
        self.assertEqual(res.data, serializer.data)

    def test_ingredient_list_limited_to_user(self):
        """Test list of ingredients is limited to authenticated user."""
        new_user = create_user(
            email="newuser@example.com",
            password="testpass123"
        )

        create_ingredient(user=new_user, name="Milk")
        create_ingredient(user=self.user, name="Butter")

        res = self.client.get(INGREDIENT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        ingredients = Ingredient.objects.filter(user=self.user)
        serializer = IngredientSerializer(ingredients, many=True)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data, serializer.data)

    def test_update_ingredient(self):
        """Test for updating an ingredient"""
        ingredient = create_ingredient(user=self.user, name="Milk")
        payload = {
            "name": "Butter"
        }
        url = detail_url(ingredient.id)

        res = self.client.patch(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.name, payload["name"])
        self.assertEqual(ingredient.user, self.user)

    def test_delete_ingredient(self):
        """test for deleting an ingredient"""
        ingredient = create_ingredient(user=self.user, name="Milk")
        url = detail_url(ingredient.id)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Ingredient.objects.filter(id=ingredient.id).exists())
