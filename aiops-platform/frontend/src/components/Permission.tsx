import React from 'react';
import { useAuth } from '../contexts/AuthContext';

interface PermissionProps {
  children: React.ReactNode;
  permission?: string | string[];
  role?: string | string[];
  fallback?: React.ReactNode;
}

const Permission: React.FC<PermissionProps> = ({ 
  children, 
  permission, 
  role,
  fallback = null 
}) => {
  const { isAdmin, hasPermission, hasRole } = useAuth();

  if (isAdmin) {
    return <>{children}</>;
  }

  if (permission) {
    const permissions = Array.isArray(permission) ? permission : [permission];
    const hasAnyPermission = permissions.some(p => hasPermission(p));
    if (!hasAnyPermission) {
      return <>{fallback}</>;
    }
  }

  if (role) {
    const roles = Array.isArray(role) ? role : [role];
    const hasAnyRole = roles.some(r => hasRole(r));
    if (!hasAnyRole) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
};

export default Permission;
