from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # email ou téléphone
    password = serializers.CharField(trim_whitespace=False)
