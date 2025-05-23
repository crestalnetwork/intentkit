# intentkit/skills/face_swapper/face_swap.py

from typing import Type
from pydantic import BaseModel, Field
import httpx

from skills.face_swapper.base import FaceSwapperBaseTool


class FaceSwapInput(BaseModel):
    """Input untuk alat face swap."""

    source_image_url: str = Field(description="URL gambar wajah sumber")
    target_image_url: str = Field(description="URL gambar target")
    api_url: str = Field(description="Endpoint API face swap pihak ketiga")
    api_key: str = Field(description="API key untuk autentikasi dengan penyedia API")


class FaceSwapTool(FaceSwapperBaseTool):
    """Alat untuk melakukan face swap dengan API pihak ketiga."""

    name: str = "face_swap"
    description: str = (
        "Swap wajah dari satu gambar ke gambar lain menggunakan layanan API eksternal."
    )
    args_schema: Type[BaseModel] = FaceSwapInput

    async def _arun(
        self,
        source_image_url: str,
        target_image_url: str,
        api_url: str,
        api_key: str,
        **kwargs,
    ) -> str:
        payload = {
            "source_image": source_image_url,
            "target_image": target_image_url,
        }
        headers = {
            "Authorization": f"Bearer {api_key}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, headers=headers)

        if response.status_code == 200:
            return response.json().get("result_url", "Success, but no result_url found.")
        else:
            return f"Error: {response.status_code} - {response.text}"
