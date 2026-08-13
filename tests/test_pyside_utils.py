import unittest
import sys
import os
import shutil
from unittest.mock import MagicMock, patch

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.batch_ops import BatchOperationManager
from utils.maintenance import MaintenanceManager
from utils.thumbnails import ThumbnailGenerator
from javsp_integration import JavSPIntegration
from javdb_crawler_single import get_attempt_configs, is_cloudflare_challenge_html
from javdb_login_helper import get_login_attempts

class TestUtils(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.cursor = MagicMock()

    def test_thumbnail_generator_path(self):
        """mock 返回什么路径就断言什么——不耦合真实环境。

        源码 get_ffmpeg_command() 会优先检查 bundled/homebrew 路径，
        用 os.path.exists=False 跳过这些环境特定分支，让 mock 完全接管。
        """
        # 跨系统选一个「不存在于常见路径」的 mock 值
        test_path = '/mock/bin/ffmpeg'
        with patch('shutil.which', return_value=test_path), \
             patch('os.path.exists', return_value=False):  # 跳过 bundled + homebrew 检测
            self.assertEqual(ThumbnailGenerator.get_ffmpeg_command(), test_path)

    def test_ffmpeg_available_in_real_env(self):
        """验证当前环境能找到 ffmpeg（不断言具体路径，跨系统兼容）。"""
        cmd = ThumbnailGenerator.get_ffmpeg_command()
        self.assertIsNotNone(cmd, "当前环境未找到 ffmpeg")
        self.assertTrue(
            os.path.isfile(cmd) or shutil.which(cmd) is not None,
            f"ffmpeg 路径无效: {cmd}"
        )
            
    def test_batch_calculate_md5(self):
        batch = BatchOperationManager(self.mock_db)
        # Mock get_videos_by_ids
        batch._get_videos_by_ids = MagicMock(return_value=[
            {'id': 1, 'file_path': '/tmp/test.mp4'}
        ])
        
        # Mock FileUtils.calculate_md5
        with patch('utils.file_utils.FileUtils.calculate_md5', return_value='hash123'):
            with patch('os.path.exists', return_value=True):
                result = batch.batch_calculate_md5([1])
                self.assertEqual(result['success'], 1)
                self.mock_db.update_video.assert_called_with(1, {'md5_hash': 'hash123'})
                
    def test_maintenance_sync_stars(self):
        maint = MaintenanceManager(self.mock_db)
        # Mock cursor.fetchall
        self.mock_db.cursor.fetchall.return_value = [
            (1, '/tmp/test.mp4', 5) # 5 stars -> !!!!test.mp4
        ]
        
        with patch('os.path.exists', return_value=True):
            with patch('utils.file_utils.FileUtils.move_file', return_value=True):
                result = maint.sync_stars_to_filename([1])
                self.assertEqual(result['renamed'], 1)
                self.mock_db.update_video.assert_called()
                # Check call args
                args = self.mock_db.update_video.call_args[0]
                self.assertEqual(args[0], 1)
                self.assertIn('!!!!test.mp4', args[1]['file_name'])

    def test_javsp_integration_search_movie_info_parallel(self):
        with patch('javsp_integration.CrawlerManager') as mock_manager_cls:
            mock_manager = MagicMock()
            mock_movie = MagicMock()
            mock_movie.dvdid = "SHKD-690"
            mock_movie.cid = None
            mock_movie.url = "https://javdb.com/v/shkd-690"
            mock_movie.title = "SHKD-690 Title"
            mock_movie.publish_date = "2024-01-01"
            mock_movie.duration = "120"
            mock_movie.producer = "Studio"
            mock_movie.publisher = None
            mock_movie.serial = "Series"
            mock_movie.score = "8.1"
            mock_movie.cover = "https://javdb.com/cover.jpg"
            mock_movie.magnet = []
            mock_movie.genre = ["tag1"]
            mock_movie.actress = ["actor1"]
            mock_movie.clean_title.return_value = "SHKD-690 Title"
            mock_manager.search_movie.return_value = mock_movie
            mock_manager_cls.return_value = mock_manager

            integration = JavSPIntegration(db_path=":memory:")
            result = integration.search_movie_info("SHKD-690", use_parallel=True)

            self.assertIsNotNone(result)
            mock_manager.search_movie.assert_called_once_with("SHKD-690", use_parallel=True)

    def test_javsp_integration_batch_search_parallel(self):
        with patch('javsp_integration.CrawlerManager') as mock_manager_cls:
            mock_manager = MagicMock()
            mock_movie = MagicMock()
            mock_movie.dvdid = "SHKD-690"
            mock_movie.cid = None
            mock_movie.url = "https://javdb.com/v/shkd-690"
            mock_movie.title = "SHKD-690 Title"
            mock_movie.publish_date = "2024-01-01"
            mock_movie.duration = "120"
            mock_movie.producer = "Studio"
            mock_movie.publisher = None
            mock_movie.serial = "Series"
            mock_movie.score = "8.1"
            mock_movie.cover = "https://javdb.com/cover.jpg"
            mock_movie.magnet = []
            mock_movie.genre = ["tag1"]
            mock_movie.actress = ["actor1"]
            mock_movie.clean_title.return_value = "SHKD-690 Title"
            mock_manager.batch_search.return_value = {"SHKD-690": mock_movie}
            mock_manager_cls.return_value = mock_manager

            integration = JavSPIntegration(db_path=":memory:")
            result = integration.batch_search_movies(["SHKD-690"], use_parallel=True)

            self.assertIn("SHKD-690", result)
            mock_manager.batch_search.assert_called_once_with(["SHKD-690"], use_parallel=True)

    def test_javdb_attempt_configs_proxy_default(self):
        """对齐源码 get_attempt_configs(True)：先非 headless 再 headless，再带 proxy。"""
        configs = get_attempt_configs(True)
        self.assertGreaterEqual(len(configs), 4)  # proxy=True → 4 个配置
        # 源码顺序：no-proxy+no-headless → no-proxy+headless → proxy+no-headless → proxy+headless
        self.assertEqual(configs[0], {"use_proxy": False, "headless": False})
        self.assertEqual(configs[1], {"use_proxy": False, "headless": True})
        self.assertTrue(any(c["use_proxy"] for c in configs))

    def test_javdb_attempt_configs_direct_default(self):
        """对齐源码 get_attempt_configs(False)：只有两个无代理配置。"""
        configs = get_attempt_configs(False)
        self.assertGreaterEqual(len(configs), 2)
        self.assertEqual(configs[0], {"use_proxy": False, "headless": False})
        self.assertEqual(configs[1], {"use_proxy": False, "headless": True})
        # proxy=False → 不应有任何代理配置
        self.assertFalse(any(c["use_proxy"] for c in configs))

    def test_cloudflare_detection_html(self):
        """对齐源码 is_cloudflare_challenge_html 的真实检测逻辑。

        源码逻辑：
          - title 含标记 + body 含标记 → True（title_markers + body_markers 联合判定）
          - title 空 → 依赖 body 中的 strong/secondary markers
          - age confirmation 页面 → False（优先排除）
        """
        # 场景 1：title="Just a moment..." 匹配 title_markers，
        #          body 含 "checking your browser" 匹配 body_markers → True
        html = "<html><title>Just a moment...</title><body>Checking your browser</body></html>"
        self.assertTrue(is_cloudflare_challenge_html(html, "Just a moment..."))

        # 场景 2：空 title 时，body 需包含完整 cf 标记（strong_markers）才能检测到。
        #   "checking your browser before accessing" 是 strong_marker → True
        html_cf = "<html><body>Checking your browser before accessing</body></html>"
        self.assertTrue(is_cloudflare_challenge_html(html_cf, ""))

        # 场景 3：正常页面（无 cf 标记）→ False
        self.assertFalse(is_cloudflare_challenge_html("<html><title>正常页面</title></html>", "正常页面"))

    def test_login_helper_attempts_no_proxy_first(self):
        attempts = get_login_attempts(False)
        self.assertGreaterEqual(len(attempts), 1)
        self.assertFalse(attempts[0]["proxy"])

    def test_environment_detection(self):
        """验证跨系统环境自检能力（macOS / Windows / Linux 均可运行）。"""
        import platform
        # ffmpeg：检测到就验证路径有效，没装也不报错（CI 可能无 ffmpeg）
        cmd = ThumbnailGenerator.get_ffmpeg_command()
        if cmd:
            self.assertTrue(os.path.isfile(cmd), f"ffmpeg 路径无效: {cmd}")
        # 平台信息可获取
        self.assertIn(platform.system(), ('Darwin', 'Windows', 'Linux'))
        # Python 版本 >= 3.8
        self.assertGreaterEqual(sys.version_info[:2], (3, 8))


if __name__ == '__main__':
    unittest.main()
