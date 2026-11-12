import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ds/primitives';

export default function NotFoundPage() {
  return (
    <div className="page">
      <EmptyState
        title="This page does not exist"
        description="The address may be old or mistyped."
        action={<Button asChild><Link to="/">Go to the overview</Link></Button>}
        className="mt-10"
      />
    </div>
  );
}
