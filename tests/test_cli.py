import unittest

from douyin_downloader.cli import build_parser, extract_url, parse_cookies_from_browser


class TestCli(unittest.TestCase):
    def test_parser_has_url(self):
        p = build_parser()
        ns = p.parse_args(["https://example.com/"])
        self.assertEqual(" ".join(ns.text), "https://example.com/")

    def test_extract_url_from_share_text(self):
        s = (
            "4.12 复制打开抖音，看看【修勾的作品】... "
            "https://v.douyin.com/0LePrfdCAW4/ ytE:/ 06/07 r@R.Kj"
        )
        self.assertEqual(extract_url(s), "https://v.douyin.com/0LePrfdCAW4/")

    def test_parse_cookies_from_browser_simple(self):
        self.assertEqual(parse_cookies_from_browser("edge"), ("edge", None, None, None))

    def test_parse_cookies_from_browser_profile(self):
        self.assertEqual(parse_cookies_from_browser("chrome:Default"), ("chrome", "Default", None, None))

    def test_help_parses_via_cdp_arg(self):
        p = build_parser()
        ns = p.parse_args(["https://example.com/", "--via-cdp", "edge"])
        self.assertEqual(ns.via_cdp, "edge")


if __name__ == "__main__":
    unittest.main()
