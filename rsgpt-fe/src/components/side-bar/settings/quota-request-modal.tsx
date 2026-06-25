'use client';

import { useState } from 'react';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Input,
  Textarea,
  Alert,
} from '@heroui/react';
import { useRequestQuota } from '@/hooks/useRequestQuota';

interface QuotaRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentQuota: number;
  currentUsed: number;
}

export function QuotaRequestModal({
  isOpen,
  onClose,
  currentQuota,
  currentUsed,
}: QuotaRequestModalProps) {
  const [requestedQuota, setRequestedQuota] = useState<string>('10');
  const [reason, setReason] = useState<string>('');
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  
  const { mutate: submitRequest, isPending } = useRequestQuota();
  
  const handleSubmit = () => {
    const quotaNum = parseInt(requestedQuota, 10);
    
    if (isNaN(quotaNum) || quotaNum < 1 || quotaNum > 100) {
      return;
    }
    
    if (reason.trim().length < 10) {
      return;
    }
    
    submitRequest(
      {
        requested_quota: quotaNum,
        reason: reason.trim(),
      },
      {
        onSuccess: () => {
          setSubmitStatus('success');
          // Reset form after short delay
          setTimeout(() => {
            setRequestedQuota('10');
            setReason('');
            setSubmitStatus('idle');
            onClose();
          }, 2000);
        },
        onError: () => {
          setSubmitStatus('error');
          setTimeout(() => setSubmitStatus('idle'), 3000);
        },
      }
    );
  };
  
  const handleClose = () => {
    if (!isPending) {
      setRequestedQuota('10');
      setReason('');
      setSubmitStatus('idle');
      onClose();
    }
  };
  
  const isValidQuota = !isNaN(parseInt(requestedQuota, 10)) && 
    parseInt(requestedQuota, 10) >= 1 && 
    parseInt(requestedQuota, 10) <= 100;
  const isValidReason = reason.trim().length >= 10;
  const canSubmit = isValidQuota && isValidReason && !isPending && submitStatus === 'idle';
  
  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="md" placement="center">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold">Request More Agent Quota</h2>
          <p className="text-sm text-default-500 font-normal">
            Current usage: {currentUsed} / {currentQuota} requests
          </p>
        </ModalHeader>
        <ModalBody className="gap-4">
          {submitStatus === 'success' && (
            <Alert color="success" variant="flat">
              Your request has been submitted! We&apos;ll review it shortly.
            </Alert>
          )}
          
          {submitStatus === 'error' && (
            <Alert color="danger" variant="flat">
              Failed to submit request. Please try again.
            </Alert>
          )}
          
          <Input
            type="number"
            label="Additional Requests Needed"
            placeholder="10"
            value={requestedQuota}
            onValueChange={setRequestedQuota}
            min={1}
            max={100}
            description="Enter a number between 1 and 100"
            isInvalid={requestedQuota !== '' && !isValidQuota}
            errorMessage={!isValidQuota && requestedQuota !== '' ? 'Must be between 1 and 100' : ''}
            isDisabled={isPending || submitStatus === 'success'}
          />
          
          <Textarea
            label="Feedback for Agent Mode"
            placeholder="Please provide feedback for the Agent Mode..."
            value={reason}
            onValueChange={setReason}
            minRows={3}
            maxRows={6}
            description={`${reason.length}/1000 characters (minimum 10)`}
            isInvalid={reason.length > 0 && !isValidReason}
            errorMessage={reason.length > 0 && !isValidReason ? 'Please provide at least 10 characters' : ''}
            maxLength={1000}
            isDisabled={isPending || submitStatus === 'success'}
          />
        </ModalBody>
        <ModalFooter>
          <Button
            color="default"
            variant="flat"
            onPress={handleClose}
            isDisabled={isPending}
          >
            Cancel
          </Button>
          <Button
            color="primary"
            onPress={handleSubmit}
            isLoading={isPending}
            isDisabled={!canSubmit}
          >
            Submit Request
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
