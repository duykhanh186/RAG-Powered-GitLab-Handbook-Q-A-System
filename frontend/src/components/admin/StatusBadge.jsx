import React from 'react';

const STATUS_MAP = {
  embedded:   { label: 'Embedded',   cls: 'badge--green'  },
  processing: { label: 'Processing', cls: 'badge--yellow' },
  uploading:  { label: 'Uploading',  cls: 'badge--blue'   },
  failed:     { label: 'Failed',     cls: 'badge--red'    },
  pending:    { label: 'Pending',    cls: 'badge--gray'   },
  active:     { label: 'Active',     cls: 'badge--green'  },
  inactive:   { label: 'Inactive',   cls: 'badge--gray'   },
  idle:       { label: 'Idle',       cls: 'badge--gray'   },
  busy:       { label: 'Busy',       cls: 'badge--yellow' },
  error:      { label: 'Error',      cls: 'badge--red'    },
  ok:         { label: 'OK',         cls: 'badge--green'  },
  online:     { label: 'Online',     cls: 'badge--green'  },
  offline:    { label: 'Offline',    cls: 'badge--red'    },
  admin:      { label: 'Admin',      cls: 'badge--purple' },
  user:       { label: 'User',       cls: 'badge--blue'   },
  unknown:    { label: 'Unknown',    cls: 'badge--gray'   },
};

function StatusBadge({ status }) {
  const key = status?.toLowerCase?.() ?? '';
  const s = STATUS_MAP[key] ?? { label: status ?? 'N/A', cls: 'badge--gray' };
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

export default StatusBadge;