import React from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button } from '@heroui/react';
import { useTheme } from 'next-themes';
import logoDark from '../assets/images/rsinsight-plus-logo-dark.svg';
import logoLight from '../assets/images/rsinsight-plus-logo-light.svg';

interface AboutModalProps {
    isOpen: boolean;
    onClose: () => void;
    appVersion: string;
}

const Logo: React.FC<{ className?: string }> = ({ className = '' }) => {
    const { theme, systemTheme } = useTheme();
    const currentTheme = theme === 'system' ? systemTheme : theme;
    const logoSrc = currentTheme === 'dark' ? logoDark : logoLight;

    return <img src={logoSrc} alt="RSInsight" className={className} />;
};

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose, appVersion }) => {
    return (
        <Modal isOpen={isOpen} onClose={onClose} placement="center">
            <ModalContent>
                {(onClose) => (
                    <>
                        <ModalHeader className="flex flex-col gap-1">About RSInsight Desktop</ModalHeader>
                        <ModalBody>
                            <div className="flex flex-col items-center gap-4 py-4">
                                <Logo className="h-16 w-auto" />
                                <div className="text-center">
                                    <p className="text-lg font-semibold">RSInsight Desktop</p>
                                    {appVersion && (
                                        <p className="text-sm text-default-500">Version {appVersion}</p>
                                    )}
                                </div>
                            </div>
                        </ModalBody>
                        <ModalFooter>
                            <Button color="primary" onPress={onClose}>
                                Close
                            </Button>
                        </ModalFooter>
                    </>
                )}
            </ModalContent>
        </Modal>
    );
};