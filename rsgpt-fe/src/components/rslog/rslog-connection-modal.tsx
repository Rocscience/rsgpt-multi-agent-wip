'use client';

import { useState, useEffect } from 'react';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Input,
  Card,
  CardBody,
  Spinner,
} from '@heroui/react';
import { EyeIcon, EyeSlashIcon, CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { RSLogIcon } from '@/components/icons/rslog-icon';
import { 
  useRSLogConnect, 
  useRSLogVerify, 
  isRSLogTwoFactorResponse,
  isRSLogErrorResponse 
} from '@/hooks/useRSLogConnection';
import type { 
  RSLogConnectTokenRequest, 
  RSLogVerifyRequest,
  RSLogTokenResponse,
  RSLogTwoFactorResponse 
} from '@/lib/types';

interface RSLogConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

type ModalStep = 'credentials' | 'twoFactor' | 'success' | 'error';

interface FormData {
  username: string;
  password: string;
  company: string;
  twoFactorCode: string;
}

export const RSLogConnectionModal = ({ isOpen, onClose, onSuccess }: RSLogConnectionModalProps) => {
  const [step, setStep] = useState<ModalStep>('credentials');
  const [formData, setFormData] = useState<FormData>({
    username: '',
    password: '',
    company: '',
    twoFactorCode: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [twoFactorInfo, setTwoFactorInfo] = useState<RSLogTwoFactorResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  const connectMutation = useRSLogConnect();
  const verifyMutation = useRSLogVerify();

  // Reset form when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setStep('credentials');
      setFormData({
        username: '',
        password: '',
        company: '',
        twoFactorCode: '',
      });
      setTwoFactorInfo(null);
      setErrorMessage('');
      setShowPassword(false);
    }
  }, [isOpen]);

  const handleCredentialsSubmit = async () => {
    if (!formData.username || !formData.password || !formData.company) {
      setErrorMessage('Please fill in all fields');
      return;
    }

    // Basic validation
    if (formData.username.length < 3) {
      setErrorMessage('Username must be at least 3 characters long');
      return;
    }

    if (formData.company.length < 2) {
      setErrorMessage('Company name must be at least 2 characters long');
      return;
    }

    setErrorMessage('');
    
    const request: RSLogConnectTokenRequest = {
      username: formData.username,
      password: formData.password,
      company: formData.company,
    };

    try {
      const result = await connectMutation.mutateAsync(request);
      
      if (isRSLogTwoFactorResponse(result)) {
        // 2FA required
        setTwoFactorInfo(result);
        setStep('twoFactor');
      } else {
        // Success - token received
        setStep('success');
        setTimeout(async () => {
          if (onSuccess) {
            await onSuccess();
          }
          onClose();
        }, 2000);
      }
    } catch (error: any) {
      console.error('RSLog connection error:', error);
      
      if (error.message && typeof error.message === 'string') {
        try {
          const errorData = JSON.parse(error.message);
          if (errorData.detail && typeof errorData.detail === 'object') {
            setErrorMessage(errorData.detail.errorDescription || errorData.detail.error || 'Connection failed');
          } else {
            setErrorMessage(errorData.detail || error.message);
          }
        } catch {
          setErrorMessage(error.message);
        }
      } else {
        setErrorMessage('Failed to connect to RSLog. Please check your credentials.');
      }
      setStep('error');
    }
  };

  const handleTwoFactorSubmit = async () => {
    if (!formData.twoFactorCode) {
      setErrorMessage('Please enter the verification code');
      return;
    }

    setErrorMessage('');

    const request: RSLogVerifyRequest = {
      username: formData.username,
      password: formData.password,
      company: formData.company,
      twoFactorCode: formData.twoFactorCode,
    };

    try {
      await verifyMutation.mutateAsync(request);
      setStep('success');
      setTimeout(async () => {
        if (onSuccess) {
          await onSuccess();
        }
        onClose();
      }, 2000);
    } catch (error: any) {
      console.error('RSLog 2FA error:', error);
      
      if (error.message && typeof error.message === 'string') {
        try {
          const errorData = JSON.parse(error.message);
          if (errorData.detail && typeof errorData.detail === 'object') {
            setErrorMessage(errorData.detail.errorDescription || errorData.detail.error || 'Verification failed');
          } else {
            setErrorMessage(errorData.detail || error.message);
          }
        } catch {
          setErrorMessage(error.message);
        }
      } else {
        setErrorMessage('Invalid verification code. Please try again.');
      }
    }
  };

  const handleRetry = () => {
    setStep('credentials');
    setErrorMessage('');
    setTwoFactorInfo(null);
    setFormData(prev => ({ ...prev, twoFactorCode: '' }));
  };

  const isLoading = connectMutation.isPending || verifyMutation.isPending;

  const renderCredentialsStep = () => (
    <>
      <ModalHeader className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <RSLogIcon className="w-8 h-8" />
          <div>
            <h2 className="text-xl font-semibold">Connect to RSLog</h2>
            <p className="text-sm text-default-500 font-normal">
              Enter your RSLog credentials to connect your account
            </p>
          </div>
        </div>
      </ModalHeader>
      <ModalBody>
        <div className="flex flex-col gap-4">
          <Input
            label="Username or Email"
            placeholder="Enter your RSLog username or email"
            value={formData.username}
            onChange={(e) => setFormData(prev => ({ ...prev, username: e.target.value }))}
            isRequired
            variant="bordered"
          />
          <Input
            label="Password"
            placeholder="Enter your RSLog password"
            type={showPassword ? 'text' : 'password'}
            value={formData.password}
            onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
            isRequired
            variant="bordered"
            endContent={
              <button
                className="focus:outline-none"
                type="button"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeSlashIcon className="w-5 h-5 text-default-400" />
                ) : (
                  <EyeIcon className="w-5 h-5 text-default-400" />
                )}
              </button>
            }
          />
          <Input
            label="Company"
            placeholder="Enter your company/tenant name"
            value={formData.company}
            onChange={(e) => setFormData(prev => ({ ...prev, company: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !isLoading && formData.username && formData.password && formData.company) {
                handleCredentialsSubmit();
              }
            }}
            isRequired
            variant="bordered"
          />
          {errorMessage && (
            <Card className="bg-danger-50 border-danger-200">
              <CardBody className="py-3">
                <div className="flex items-center gap-2">
                  <ExclamationTriangleIcon className="w-5 h-5 text-danger-500 flex-shrink-0" />
                  <p className="text-sm text-danger-700">{errorMessage}</p>
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </ModalBody>
      <ModalFooter>
        <Button variant="light" onPress={onClose} isDisabled={isLoading}>
          Cancel
        </Button>
        <Button 
          color="primary" 
          onPress={handleCredentialsSubmit}
          isLoading={isLoading}
          isDisabled={!formData.username || !formData.password || !formData.company}
        >
          Connect
        </Button>
      </ModalFooter>
    </>
  );

  const renderTwoFactorStep = () => (
    <>
      <ModalHeader className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <RSLogIcon className="w-8 h-8" />
          <div>
            <h2 className="text-xl font-semibold">Two-Factor Authentication</h2>
            <p className="text-sm text-default-500 font-normal">
              Enter the verification code sent to your email
            </p>
          </div>
        </div>
      </ModalHeader>
      <ModalBody>
        <div className="flex flex-col gap-4">
          {twoFactorInfo && (
            <Card className="bg-primary-50 border-primary-200">
              <CardBody className="py-3">
                <p className="text-sm text-primary-700">
                  {twoFactorInfo.message}
                </p>
                <p className="text-xs text-primary-600 mt-1">
                  Sent to: {twoFactorInfo.maskedEmail}
                </p>
              </CardBody>
            </Card>
          )}
          <Input
            label="Verification Code"
            placeholder="Enter the 6-digit code"
            value={formData.twoFactorCode}
            onChange={(e) => setFormData(prev => ({ ...prev, twoFactorCode: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !isLoading && formData.twoFactorCode) {
                handleTwoFactorSubmit();
              }
            }}
            isRequired
            variant="bordered"
            maxLength={6}
          />
          {errorMessage && (
            <Card className="bg-danger-50 border-danger-200">
              <CardBody className="py-3">
                <div className="flex items-center gap-2">
                  <ExclamationTriangleIcon className="w-5 h-5 text-danger-500 flex-shrink-0" />
                  <p className="text-sm text-danger-700">{errorMessage}</p>
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </ModalBody>
      <ModalFooter>
        <Button variant="light" onPress={handleRetry} isDisabled={isLoading}>
          Back
        </Button>
        <Button 
          color="primary" 
          onPress={handleTwoFactorSubmit}
          isLoading={isLoading}
          isDisabled={!formData.twoFactorCode}
        >
          Verify
        </Button>
      </ModalFooter>
    </>
  );

  const renderSuccessStep = () => (
    <>
      <ModalHeader className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <CheckCircleIcon className="w-8 h-8 text-success-500" />
          <div>
            <h2 className="text-xl font-semibold text-success-600">Connected Successfully!</h2>
            <p className="text-sm text-default-500 font-normal">
              Your RSLog account has been connected
            </p>
          </div>
        </div>
      </ModalHeader>
      <ModalBody>
        <Card className="bg-success-50 border-success-200">
          <CardBody className="py-4 text-center">
            <p className="text-success-700">
              RSLog is now available in Agent Mode. You can access RSLog data and functionality 
              through the additional settings menu.
            </p>
          </CardBody>
        </Card>
      </ModalBody>
      <ModalFooter>
        <Button color="success" onPress={onClose} className="w-full">
          Done
        </Button>
      </ModalFooter>
    </>
  );

  const renderErrorStep = () => (
    <>
      <ModalHeader className="flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <ExclamationTriangleIcon className="w-8 h-8 text-danger-500" />
          <div>
            <h2 className="text-xl font-semibold text-danger-600">Connection Failed</h2>
            <p className="text-sm text-default-500 font-normal">
              Unable to connect to RSLog
            </p>
          </div>
        </div>
      </ModalHeader>
      <ModalBody>
        <Card className="bg-danger-50 border-danger-200">
          <CardBody className="py-4">
            <p className="text-danger-700 text-sm">
              {errorMessage || 'An unexpected error occurred. Please try again.'}
            </p>
          </CardBody>
        </Card>
      </ModalBody>
      <ModalFooter>
        <Button variant="light" onPress={onClose}>
          Cancel
        </Button>
        <Button color="primary" onPress={handleRetry}>
          Try Again
        </Button>
      </ModalFooter>
    </>
  );

  const renderModalContent = () => {
    switch (step) {
      case 'credentials':
        return renderCredentialsStep();
      case 'twoFactor':
        return renderTwoFactorStep();
      case 'success':
        return renderSuccessStep();
      case 'error':
        return renderErrorStep();
      default:
        return renderCredentialsStep();
    }
  };

  return (
    <Modal 
      isOpen={isOpen} 
      onClose={onClose}
      size="md"
      placement="center"
      isDismissable={!isLoading}
      hideCloseButton={isLoading}
    >
      <ModalContent>
        {renderModalContent()}
      </ModalContent>
    </Modal>
  );
};
