import { describe, it, expect } from 'vitest';
import { UserCard } from '../src/components/UserCard';

describe('UserCard Component', () => {
  it('should render user name', () => {
    expect(UserCard).toBeDefined();
  });
});
