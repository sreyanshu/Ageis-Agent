import React from 'react';
import { fetchUsers } from '../api/userClient';

export interface UserCardProps {
  userId: number;
  name: string;
}

export function UserCard(props: UserCardProps) {
  return (
    <div className="user-card">
      <h3>{props.name}</h3>
      <button onClick={() => fetchUsers()}>Refresh</button>
    </div>
  );
}
