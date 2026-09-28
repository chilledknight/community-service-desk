"""Tests for Accessibility (A11y) and Responsive UI baselines."""

from pathlib import Path


def test_base_template_accessibility():
    template_path = Path("community_service_desk/web/templates/base.html")
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    # 1. Must include semantic skip link for keyboard navigation
    assert 'class="skip-link"' in content
    assert 'href="#main-content"' in content

    # 2. Must include lang attribute on <html>
    assert '<html lang="en">' in content

    # 3. Must include responsive viewport meta tag
    assert 'name="viewport"' in content
    assert "width=device-width" in content

    # 4. Must declare landmark roles
    assert 'role="banner"' in content
    assert 'role="main"' in content
    assert 'role="contentinfo"' in content


def test_login_template_labels_and_accessibility():
    template_path = Path("community_service_desk/web/templates/login.html")
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    # Labels associated with inputs
    assert '<label for="email">' in content
    assert '<input type="email" id="email"' in content
    assert '<label for="password">' in content
    assert '<input type="password" id="password"' in content


def test_ticket_detail_internal_notes_unmistakable():
    template_path = Path("community_service_desk/web/templates/ticket_detail.html")
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    # Internal notes have visually unmistakable badge and class
    assert "internal-note" in content
    assert "INTERNAL NOTE &bull; STAFF ONLY" in content
    assert 'role="region"' in content


def test_stylesheet_responsive_breakpoints():
    css_path = Path("community_service_desk/static/css/style.css")
    assert css_path.exists()
    css = css_path.read_text(encoding="utf-8")

    # Focus indicator for keyboard navigation
    assert ":focus-visible" in css
    assert "outline" in css

    # Responsive breakpoints for desktop, 390px, and 320px
    assert "@media (max-width: 900px)" in css
    assert "@media (max-width: 640px)" in css
    assert "@media (max-width: 390px)" in css
    assert "@media (max-width: 320px)" in css

    # Internal notes styling
    assert "--note-bg" in css
    assert "--note-border" in css
