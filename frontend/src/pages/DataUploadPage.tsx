import React, { useState } from 'react';
import { format } from 'date-fns';
import { useDataQuality } from '../hooks/useData';
import { cn, formatNumber, parseServerTimestamp } from '../utils/helpers';
import {
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  XCircle,
  RefreshCw,
  Trash2,
  Eye,
} from 'lucide-react';

export function DataUploadPage() {
  const { data: reports, loading, upload, refetch } = useDataQuality();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<any[]>([]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadError(null);
      setUploadResult(null);
      setSelectedFile(e.dataTransfer.files[0]);
      previewFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setUploadError(null);
      setUploadResult(null);
      setSelectedFile(e.target.files[0]);
      previewFile(e.target.files[0]);
    }
  };

  const previewFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.trim().split('\n');
      const headers = lines[0].split(',').map(h => h.trim());
      const preview = lines.slice(1, 21).map(line => {
        const values = line.split(',').map(v => v.trim());
        return headers.reduce((obj, header, index) => {
          obj[header] = values[index] || '';
          return obj;
        }, {} as any);
      });
      setPreviewData(preview);
      setShowPreview(true);
    };
    reader.readAsText(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      const result = await upload(selectedFile); // the hook refetches the report list
      setUploadResult(result);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setUploadResult(null);
    setUploadError(null);
    setShowPreview(false);
    setPreviewData([]);
  };

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'COMPLETED': return 'bg-success-100 text-success-700';
      case 'FAILED': return 'bg-danger-100 text-danger-700';
      case 'PROCESSING': return 'bg-warning-100 text-warning-700';
      default: return 'bg-secondary-100 text-secondary-700';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'COMPLETED': return <CheckCircle className="w-4 h-4" />;
      case 'FAILED': return <XCircle className="w-4 h-4" />;
      case 'PROCESSING': return <AlertCircle className="w-4 h-4" />;
      default: return <AlertCircle className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Upload Dataset</h1>
          <p className="text-secondary-500">Upload CSV files for production planning data</p>
        </div>
        <button onClick={refetch} className="btn-secondary" disabled={loading}>
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Upload Zone */}
      <div className={cn(
        'card p-8 border-2 border-dashed rounded-xl transition-colors',
        dragActive ? 'border-primary-500 bg-primary-50' : 'border-secondary-300 hover:border-primary-400'
      )}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
      >
        {!selectedFile ? (
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-primary-100 flex items-center justify-center">
              <Upload className="w-8 h-8 text-primary-600" />
            </div>
            <h3 className="text-lg font-medium text-secondary-900 mb-2">Drop CSV file here or click to browse</h3>
            <p className="text-secondary-500 mb-6">Supports production planning data with orders, machines, workers, and inventory</p>
            <label className="btn-primary cursor-pointer">
              <Upload className="w-4 h-4" />
              Choose File
              <input type="file" accept=".csv" onChange={handleFileSelect} className="hidden" />
            </label>
            <p className="text-xs text-secondary-400 mt-4">Max file size: 10MB • CSV format only</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-secondary-50 rounded-lg">
              <div className="flex items-center gap-4">
                <FileText className="w-10 h-10 text-primary-600" />
                <div>
                  <p className="font-medium text-secondary-900">{selectedFile.name}</p>
                  <p className="text-sm text-secondary-500">{(selectedFile.size / 1024).toFixed(1)} KB • CSV</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => setShowPreview(!showPreview)} className="btn-secondary text-sm">
                  <Eye className="w-4 h-4" />
                  {showPreview ? 'Hide' : 'Preview'}
                </button>
                <button onClick={clearFile} className="btn-secondary text-sm">
                  <Trash2 className="w-4 h-4" />
                  Remove
                </button>
              </div>
            </div>

            {uploadResult && (
              <div className="p-4 rounded-lg bg-secondary-50 border border-secondary-200">
                <h4 className="font-medium text-secondary-900 mb-3">Upload Result</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div className="text-center p-3 bg-white rounded">
                    <p className="text-2xl font-bold text-secondary-900">{uploadResult.total_rows?.toLocaleString() || 0}</p>
                    <p className="text-xs text-secondary-500">Rows</p>
                  </div>
                  <div className="text-center p-3 bg-white rounded">
                    <p className="text-2xl font-bold text-secondary-900">{uploadResult.total_columns || 0}</p>
                    <p className="text-xs text-secondary-500">Columns</p>
                  </div>
                  <div className="text-center p-3 bg-white rounded">
                    <p className="text-2xl font-bold text-warning-600">{uploadResult.missing_values?.toLocaleString() || 0}</p>
                    <p className="text-xs text-secondary-500">Missing</p>
                  </div>
                  <div className="text-center p-3 bg-white rounded">
                    <p className="text-2xl font-bold text-primary-600">{uploadResult.quality_score?.toFixed(1) || 0}%</p>
                    <p className="text-xs text-secondary-500">Quality</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={cn('px-3 py-1 rounded-full text-sm font-medium', getStatusColor(uploadResult.status))}>
                    {getStatusIcon(uploadResult.status)} {uploadResult.status}
                  </span>
                  {uploadResult.error_message && (
                    <span className="text-sm text-danger-600">{uploadResult.error_message}</span>
                  )}
                </div>
              </div>
            )}

            {showPreview && previewData.length > 0 && (
              <div className="table-container max-h-64">
                <table className="table text-xs">
                  <thead>
                    <tr>
                      {Object.keys(previewData[0]).map(key => <th key={key} className="px-2 py-1">{key}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((val, j) => <td key={j} className="px-2 py-1">{String(val).slice(0, 30)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {uploadError && (
              <p role="alert" className="rounded-lg border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700">
                Upload failed: {uploadError}
              </p>
            )}
            <div className="flex justify-end gap-3 pt-4 border-t border-secondary-200">
              <button onClick={clearFile} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleUpload} disabled={uploading || !selectedFile} className="btn-primary">
                {uploading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                    Uploading...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Upload className="w-4 h-4" />
                    Process Dataset
                  </span>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Upload History */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">Upload History</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Filename</th>
                <th>Rows</th>
                <th>Columns</th>
                <th>Missing</th>
                <th>Duplicates</th>
                <th>Invalid</th>
                <th>Outliers</th>
                <th>Quality Score</th>
                <th>Status</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {reports?.map((report, index) => (
                <tr key={index}>
                  <td className="font-mono text-sm">{report.report_id}</td>
                  <td>{report.filename}</td>
                  <td>{formatNumber(report.total_rows)}</td>
                  <td>{report.total_columns}</td>
                  <td>{formatNumber(report.missing_values)}</td>
                  <td>{formatNumber(report.duplicate_rows)}</td>
                  <td>{formatNumber(report.invalid_records)}</td>
                  <td>{formatNumber(report.outliers)}</td>
                  <td className="font-medium">{report.quality_score.toFixed(1)}%</td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getStatusColor(report.status))}>
                      {getStatusIcon(report.status)} {report.status}
                    </span>
                  </td>
                  <td className="text-sm text-secondary-500">{format(parseServerTimestamp(report.created_at), 'MMM d, yyyy HH:mm')}</td>
                </tr>
              ))}
              {reports?.length === 0 && (
                <tr>
                  <td colSpan={11} className="text-center py-8 text-secondary-500">No uploads yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
