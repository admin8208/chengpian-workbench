
import { http } from './http'
import type { CloudConfig, CloudTestResult, CloudListResult, CloudImportResult } from './types'

export const cloudApi = {
  testConnection: (storageType: string, config: CloudConfig) =>
    http<CloudTestResult>('/api/cloud/test', {
      method: 'POST',
      body: JSON.stringify({ storage_type: storageType, name: '', config }),
    }),

  listFiles: (storageType: string, config: CloudConfig, path = '/') =>
    http<CloudListResult>('/api/cloud/list', {
      method: 'POST',
      body: JSON.stringify({ storage_type: storageType, config, path }),
    }),

  importFile: (storageType: string, config: CloudConfig, remotePath: string, fileId = '', kind = 'image') =>
    http<CloudImportResult>('/api/cloud/import', {
      method: 'POST',
      body: JSON.stringify({ 
        storage_type: storageType, 
        config, 
        remote_path: remotePath,
        file_id: fileId,
        kind,
      }),
    }),
}
