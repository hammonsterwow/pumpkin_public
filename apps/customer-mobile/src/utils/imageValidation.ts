const IMAGE_DATA_URL_PATTERN = /^data:image\/(jpeg|jpg|png);base64,[A-Za-z0-9+/=]+$/i;
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

export function validateFaceImageData(imageData: string): string[] {
  const errors: string[] = [];
  const trimmed = imageData.trim();

  if (!IMAGE_DATA_URL_PATTERN.test(trimmed)) {
    errors.push('JPEG 또는 PNG Base64 Data URL이 필요합니다.');
    return errors;
  }

  const base64 = trimmed.slice(trimmed.indexOf(',') + 1);
  const estimatedBytes = Math.floor((base64.length * 3) / 4);
  if (estimatedBytes > MAX_IMAGE_BYTES) {
    errors.push('얼굴 이미지는 장당 8MB 이하여야 합니다.');
  }

  return errors;
}

export function isFaceImageDataValid(imageData: string): boolean {
  return validateFaceImageData(imageData).length === 0;
}
