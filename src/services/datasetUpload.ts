import { defaultUploadPolicy, type UploadPolicy } from '../types'

export interface DatasetUploadSelection {
  file: File
  sheetName?: string
}

export function validateUpload(file: Pick<File, 'name' | 'size'>, policy: UploadPolicy = defaultUploadPolicy): string | null {
  const extension = '.' + file.name.split('.').at(-1)?.toLowerCase()
  if (!policy.extensions.includes(extension)) return 'Choose a ' + policy.extensions.join(', ') + ' file.'
  if (!file.size) return 'The selected file is empty.'
  if (file.size > policy.max_upload_bytes) return 'The file exceeds the upload limit of ' + Math.round(policy.max_upload_bytes / 1024 / 1024) + ' MB.'
  return null
}

