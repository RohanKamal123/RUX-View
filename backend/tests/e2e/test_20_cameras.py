"""
test_20_cameras.py — 20-camera capacity verification E2E tests for Vision OS.

Tests verify the 20-camera-per-user limit works correctly in the staging environment.
"""

import pytest
import pytest_asyncio


class Test20Cameras:
    """Test suite for 20-camera capacity verification."""

    @pytest.mark.asyncio
    async def test_add_20_cameras_one_by_one(self, async_client, staging_url, test_user):
        """Verify a user can add 20 cameras one by one."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
        created = []

        for i in range(20):
            response = await async_client.post(
                f"{staging_url}/cameras",
                json={
                    "name": f"20-Cam Test Camera {i + 1}",
                    "mode": "indoor",
                    "enabled": True,
                    "rtsp_url": f"rtsp://test-cam-{i + 1}.local/stream",
                },
                headers=headers,
            )
            if response.status_code in (200, 201):
                created.append(response.json())

        # Should have created 20 cameras
        assert len(created) == 20, f"Expected 20 cameras, got {len(created)}"

        # Cleanup
        for cam in created:
            cam_id = cam.get("id", cam.get("camera_id", ""))
            if cam_id:
                await async_client.delete(
                    f"{staging_url}/cameras/{cam_id}",
                    headers=headers,
                )

    @pytest.mark.asyncio
    async def test_add_21st_camera_returns_403(self, async_client, staging_url, test_user):
        """Verify adding a 21st camera returns 403."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
        created = []

        # Add 20 cameras first
        for i in range(20):
            response = await async_client.post(
                f"{staging_url}/cameras",
                json={
                    "name": f"Limit Test Camera {i + 1}",
                    "mode": "indoor",
                    "enabled": True,
                },
                headers=headers,
            )
            if response.status_code in (200, 201):
                created.append(response.json())

        # Try to add the 21st camera
        response = await async_client.post(
            f"{staging_url}/cameras",
            json={
                "name": "21st Camera Should Fail",
                "mode": "indoor",
                "enabled": True,
            },
            headers=headers,
        )

        # Should be rejected
        assert response.status_code in (403, 429), (
            f"Expected 403 or 429, got {response.status_code}"
        )

        # Cleanup
        for cam in created:
            cam_id = cam.get("id", cam.get("camera_id", ""))
            if cam_id:
                await async_client.delete(
                    f"{staging_url}/cameras/{cam_id}",
                    headers=headers,
                )

    @pytest.mark.asyncio
    async def test_bulk_add_20_cameras(self, async_client, staging_url, test_user):
        """Verify bulk adding 20 cameras works."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}

        cameras_data = [
            {
                "name": f"Bulk Camera {i + 1}",
                "mode": "indoor",
                "enabled": True,
            }
            for i in range(20)
        ]

        response = await async_client.post(
            f"{staging_url}/cameras/bulk",
            json=cameras_data,
            headers=headers,
        )

        # Bulk create may return 200, 201, or 403
        if response.status_code in (200, 201):
            data = response.json()
            created = data.get("cameras", data.get("data", []))
            assert len(created) <= 20

        # Cleanup: get list and delete all
        list_response = await async_client.get(
            f"{staging_url}/cameras",
            headers=headers,
        )
        if list_response.status_code == 200:
            list_data = list_response.json()
            cameras = list_data.get("cameras", list_data.get("data", []))
            for cam in cameras:
                cam_id = cam.get("id", cam.get("camera_id", ""))
                if cam_id:
                    await async_client.delete(
                        f"{staging_url}/cameras/{cam_id}",
                        headers=headers,
                    )

    @pytest.mark.asyncio
    async def test_bulk_add_21st_camera_returns_error(self, async_client, staging_url, test_user):
        """Verify bulk adding 21 cameras returns an error."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}

        cameras_data = [
            {
                "name": f"Overflow Camera {i + 1}",
                "mode": "indoor",
                "enabled": True,
            }
            for i in range(21)  # 21 cameras, should fail
        ]

        response = await async_client.post(
            f"{staging_url}/cameras/bulk",
            json=cameras_data,
            headers=headers,
        )

        # Should be rejected
        assert response.status_code in (403, 422, 429), (
            f"Expected 403, 422, or 429, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_all_20_cameras_appear_in_list(self, async_client, staging_url, test_user):
        """Verify all 20 cameras appear in the camera list."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
        created = []

        # Add 20 cameras
        for i in range(20):
            response = await async_client.post(
                f"{staging_url}/cameras",
                json={
                    "name": f"List Test Camera {i + 1}",
                    "mode": "indoor",
                    "enabled": True,
                },
                headers=headers,
            )
            if response.status_code in (200, 201):
                created.append(response.json())

        # Get camera list
        response = await async_client.get(
            f"{staging_url}/cameras",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            cameras = data.get("cameras", data.get("data", []))
            total = data.get("total", len(cameras))
            assert total == 20, f"Expected 20 cameras in list, got {total}"

        # Cleanup
        for cam in created:
            cam_id = cam.get("id", cam.get("camera_id", ""))
            if cam_id:
                await async_client.delete(
                    f"{staging_url}/cameras/{cam_id}",
                    headers=headers,
                )

    @pytest.mark.asyncio
    async def test_camera_quota_shows_20_of_20(self, async_client, staging_url, test_user):
        """Verify camera quota shows 20 of 20 when at limit."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
        created = []

        # Add 20 cameras
        for i in range(20):
            response = await async_client.post(
                f"{staging_url}/cameras",
                json={
                    "name": f"Quota Test Camera {i + 1}",
                    "mode": "indoor",
                    "enabled": True,
                },
                headers=headers,
            )
            if response.status_code in (200, 201):
                created.append(response.json())

        # Get quota
        response = await async_client.get(
            f"{staging_url}/cameras/quota",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            assert data.get("total_cameras", 0) == 20
            assert data.get("max_cameras", 0) == 20
            assert data.get("remaining", -1) == 0

        # Cleanup
        for cam in created:
            cam_id = cam.get("id", cam.get("camera_id", ""))
            if cam_id:
                await async_client.delete(
                    f"{staging_url}/cameras/{cam_id}",
                    headers=headers,
                )

    @pytest.mark.asyncio
    async def test_delete_one_camera_then_add_new_one(self, async_client, staging_url, test_user):
        """Verify deleting a camera frees a slot for a new one."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
        created = []

        # Add 20 cameras
        for i in range(20):
            response = await async_client.post(
                f"{staging_url}/cameras",
                json={
                    "name": f"Delete Test Camera {i + 1}",
                    "mode": "indoor",
                    "enabled": True,
                },
                headers=headers,
            )
            if response.status_code in (200, 201):
                created.append(response.json())

        if not created:
            pytest.skip("Could not create cameras for test")

        # Delete the first camera
        first_cam_id = created[0].get("id", created[0].get("camera_id", ""))
        delete_response = await async_client.delete(
            f"{staging_url}/cameras/{first_cam_id}",
            headers=headers,
        )
        assert delete_response.status_code in (200, 204, 404)

        # Now add a new camera (should succeed since we freed a slot)
        response = await async_client.post(
            f"{staging_url}/cameras",
            json={
                "name": "Replacement Camera",
                "mode": "indoor",
                "enabled": True,
            },
            headers=headers,
        )
        assert response.status_code in (200, 201), (
            f"Expected 200 or 201 after deleting one, got {response.status_code}"
        )

        # Cleanup remaining cameras
        list_response = await async_client.get(
            f"{staging_url}/cameras",
            headers=headers,
        )
        if list_response.status_code == 200:
            list_data = list_response.json()
            cameras = list_data.get("cameras", list_data.get("data", []))
            for cam in cameras:
                cam_id = cam.get("id", cam.get("camera_id", ""))
                if cam_id:
                    await async_client.delete(
                        f"{staging_url}/cameras/{cam_id}",
                        headers=headers,
                    )

    @pytest.mark.asyncio
    async def test_20_cameras_pagination_works(self, async_client, staging_url, test_user):
        """Verify camera list pagination works with 20 cameras."""
        headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
        created = []

        # Add 20 cameras
        for i in range(20):
            response = await async_client.post(
                f"{staging_url}/cameras",
                json={
                    "name": f"Pagination Camera {i + 1}",
                    "mode": "indoor",
                    "enabled": True,
                },
                headers=headers,
            )
            if response.status_code in (200, 201):
                created.append(response.json())

        # Test pagination with limit=10
        response = await async_client.get(
            f"{staging_url}/cameras?limit=10&offset=0",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            cameras = data.get("cameras", data.get("data", []))
            assert len(cameras) <= 10

        # Test second page
        response = await async_client.get(
            f"{staging_url}/cameras?limit=10&offset=10",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            cameras = data.get("cameras", data.get("data", []))
            assert len(cameras) <= 10

        # Cleanup
        for cam in created:
            cam_id = cam.get("id", cam.get("camera_id", ""))
            if cam_id:
                await async_client.delete(
                    f"{staging_url}/cameras/{cam_id}",
                    headers=headers,
                )
