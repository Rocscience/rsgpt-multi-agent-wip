'use client';

import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button } from "@heroui/react";

interface DeleteSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  sessionTitle: string;
  isDeleting: boolean;
}

const MAX_TITLE_LENGTH = 50;

export function DeleteSessionModal({ 
  isOpen, 
  onClose, 
  onConfirm, 
  sessionTitle,
  isDeleting 
}: DeleteSessionModalProps) {
  const displayTitle = sessionTitle.length > MAX_TITLE_LENGTH 
    ? `${sessionTitle.slice(0, MAX_TITLE_LENGTH)}...` 
    : sessionTitle;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm" placement="center">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          Delete Chat
        </ModalHeader>
        <ModalBody>
          <p className="text-default-600 break-words">
            Are you sure you want to delete <span className="font-semibold text-foreground">&quot;{displayTitle}&quot;</span>?
          </p>
          <p className="text-sm text-default-400">
            This action cannot be undone.
          </p>
        </ModalBody>
        <ModalFooter>
          <Button 
            color="default" 
            variant="flat" 
            onPress={onClose}
            isDisabled={isDeleting}
          >
            Cancel
          </Button>
          <Button 
            color="danger" 
            onPress={onConfirm}
            isLoading={isDeleting}
          >
            Delete
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

