import { CheckCircleIcon, XCircleIcon, WrenchScrewdriverIcon } from '@heroicons/react/24/outline'
import { Modal, Button } from '../ui'
import { textColors } from '../../styles/designSystem'
import type { VerifyResult } from '../../lib/api'

interface VerifyResultModalProps {
  result: VerifyResult
  onClose: () => void
}

export function VerifyResultModal({ result, onClose }: VerifyResultModalProps) {
  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Verify Result"
      maxWidth="lg"
    >
      <div className="space-y-4">
        {result.success ? (
          <>
            <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <CheckCircleIcon className="w-6 h-6 text-green-600 dark:text-green-400 flex-shrink-0" />
              <div>
                <h4 className="font-medium text-green-800 dark:text-green-200">
                  Connection Successful
                </h4>
                <p className="text-sm text-green-700 dark:text-green-300">
                  Successfully connected to the MCP server and retrieved tool list.
                </p>
              </div>
            </div>

            {result.tools && result.tools.length > 0 && (
              <div>
                <h4 className={`font-medium ${textColors.primary} mb-3 flex items-center gap-2`}>
                  <WrenchScrewdriverIcon className="w-5 h-5" />
                  Available Tools ({result.tools.length})
                </h4>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {result.tools.map((tool, index) => (
                    <div
                      key={index}
                      className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
                    >
                      <h5 className={`font-mono font-medium ${textColors.primary}`}>
                        {tool.name}
                      </h5>
                      {tool.description && (
                        <p className={`text-sm ${textColors.secondary} mt-1`}>
                          {tool.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.tools && result.tools.length === 0 && (
              <p className={`${textColors.secondary}`}>
                No tools available from this server.
              </p>
            )}
          </>
        ) : (
          <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
            <XCircleIcon className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-red-800 dark:text-red-200">
                Connection Failed
              </h4>
              {result.error && (
                <p className="text-sm text-red-700 dark:text-red-300 mt-1 font-mono">
                  {result.error}
                </p>
              )}
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2">
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </Modal>
  )
}
