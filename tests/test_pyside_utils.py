import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.batch_ops import BatchOperationManager
from utils.maintenance import MaintenanceManager
from utils.thumbnails import ThumbnailGenerator

class TestUtils(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.cursor = MagicMock()
        
    def test_thumbnail_generator_path(self):
        # Test if it finds ffmpeg (mocking shutil.which)
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            self.assertEqual(ThumbnailGenerator.get_ffmpeg_command(), '/usr/bin/ffmpeg')
            
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

if __name__ == '__main__':
    unittest.main()
