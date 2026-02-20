'use client';

import { ColumnDef } from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ArrowUpDown, CloudDownload } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export type Report = {
  report_id: string;
  blob_url: string;
  session_id: string;
};

export const columns: ColumnDef<Report>[] = [
  {
    id: 'select',
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && 'indeterminate')}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: 'session_id',
    header: ({ column }) => {
      return (
        <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
          Report ID
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      );
    },
    cell: ({ row }) => <Badge className="bg-blue-200 text-blue-700">{row.original.session_id}</Badge>,
  },
  {
    id: 'actions',
    header: 'Action',
    cell: ({ row }) => {
      const handleDownload = () => {
        let url = row.original.blob_url;
        if (!url) return;

        // If it's a local file URL or Supabase storage upload failed, use the backend download API
        if (url.startsWith('file://')) {
          const filename = url.split('/').pop() || url.split('\\').pop();
          if (filename) {
            url = `http://localhost:8000/api/reports/download/${filename}`;
          }
        }

        // Create a temporary link and click it to trigger download
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', '');
        link.setAttribute('rel', 'noopener noreferrer');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      };
      return (
        <Button size="sm" onClick={handleDownload}>
          Download Report
          <CloudDownload className="ml-2 h-4 w-4" />
        </Button>
      );
    },
  },
];
