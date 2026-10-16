import io
import tempfile
import unittest
from pathlib import Path

import httpx
from PIL import Image

from socialbot.news.extract import Article
from socialbot.news.media.source_image import candidates, credit_for, detect_agency, pick_image


def jpeg_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 80, 60)).save(buf, "JPEG")
    return buf.getvalue()


def art(url: str, image: str, site: str = "CNBC", credit: str = "") -> Article:
    return Article(url=url, final_url=url, image_url=image, sitename=site, image_credit=credit, text="x" * 400, ok=True)


class MediaTests(unittest.TestCase):
    def test_candidates_skip_logos_svgs_and_used(self):
        arts = [art("https://a.com/1", "https://cdn.a.com/static/logo-share.png"),
                art("https://b.com/1", "https://cdn.b.com/x.svg"),
                art("https://c.com/1", "https://cdn.c.com/photo.jpg"),
                art("https://d.com/1", "https://cdn.d.com/used.jpg")]
        got = [u for u, _ in candidates(arts, used={"https://cdn.d.com/used.jpg"})]
        self.assertEqual(got, ["https://cdn.c.com/photo.jpg"])

    def test_agency_detection_and_credit(self):
        self.assertEqual(detect_agency("https://image.cnbcfm.com/x-gettyimages-2297502760.jpeg"), "Getty Images")
        self.assertEqual(detect_agency("", "A protester outside the court. (AP Photo/Jane Doe)"), "AP")
        self.assertEqual(detect_agency("https://cdn.example.com/photo.jpg", "the OpenAI logo"), "")
        credit, note = credit_for("CNBC", "Getty Images")
        self.assertEqual(credit, "Photo: CNBC / Getty Images")
        self.assertIn("license", note)
        self.assertEqual(credit_for("Reuters", "Reuters")[0], "Photo: Reuters")

    def test_pick_downloads_validates_and_falls_through(self):
        big, small = jpeg_bytes(1200, 800), jpeg_bytes(300, 200)

        def handler(req: httpx.Request) -> httpx.Response:
            if "small" in str(req.url):
                return httpx.Response(200, content=small, headers={"content-type": "image/jpeg"})
            if "html" in str(req.url):
                return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})
            return httpx.Response(200, content=big, headers={"content-type": "image/jpeg"})

        http = httpx.Client(transport=httpx.MockTransport(handler))
        arts = [art("https://a.com/1", "https://cdn.a.com/small.jpg", "A"),
                art("https://b.com/1", "https://cdn.b.com/page.html", "B"),
                art("https://c.com/1", "https://cdn.c.com/gettyimages-1.jpg", "C News")]
        used: set[str] = set()
        with tempfile.TemporaryDirectory() as d:
            img = pick_image(http, arts, Path(d), used)
            self.assertIsNotNone(img)
            self.assertEqual(img.outlet, "C News")
            self.assertEqual((img.width, img.height), (1200, 800))
            self.assertEqual(img.agency, "Getty Images")
            self.assertTrue(Path(img.path).exists())
            self.assertIn("https://cdn.c.com/gettyimages-1.jpg", used)
            self.assertIsNone(pick_image(http, arts[2:], Path(d), used))     # already used on another slide
