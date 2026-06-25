import React from 'react';
import { 
  Card, 
  CardBody, 
  CardHeader, 
  Divider, 
  Avatar
} from '@heroui/react';

interface UserInfoCardProps {
  profile: UserProfile;
}

export const UserInfoCard: React.FC<UserInfoCardProps> = ({ profile }) => {
  return (
    <Card className="shadow-md min-w-fit">
      <CardHeader className="flex gap-3 items-center pb-3">
        <Avatar
          src={profile.picture}
          size="sm"
          className="border-2 border-primary"
        />
        <div className="flex flex-col">
          <h2 className="text-base font-medium text-foreground">{profile.name}</h2>
          {profile.email && profile.email !== profile.name &&(
            <span className="text-xs text-foreground/70">{profile.email}</span>
          )}
        </div>
      </CardHeader>
    </Card>
  );
};

