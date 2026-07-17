from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path("resend-verification/", views.ResendVerificationView.as_view(), name="auth-resend-verification"),
    path("password/forgot/", views.ForgotPasswordView.as_view(), name="auth-password-forgot"),
    path("password/reset/", views.ResetPasswordView.as_view(), name="auth-password-reset"),
    path("password/change/", views.ChangePasswordView.as_view(), name="auth-password-change"),
    path("sessions/", views.SessionListView.as_view(), name="auth-sessions"),
    path("sessions/revoke-others/", views.RevokeOtherSessionsView.as_view(), name="auth-sessions-revoke-others"),
    path("sessions/<int:session_id>/", views.SessionRevokeView.as_view(), name="auth-session-revoke"),
]
