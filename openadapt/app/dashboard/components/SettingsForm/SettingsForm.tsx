'use client';


import { Button, Fieldset, Flex, Grid, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form';
import React from 'react'
import { validateSettings } from './utils';
import { notifications } from '@mantine/notifications';


type Props = {
    settings: Record<string, string>,
}

export function SettingsForm ({
    settings,
}: Props) {
    const form = useForm({
        initialValues: JSON.parse(JSON.stringify(settings)),
        validate: (values) => {
            return validateSettings(values);
        },
    })

    function resetForm() {
        form.reset();
    }
    function saveSettings(values: Record<string, string>) {
        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(values),
        }).then(resp => {
            if (resp.ok) {
                notifications.show({
                    title: 'Settings saved',
                    message: 'Your settings have been saved',
                    color: 'green',
                });
                return resp.json();
            } else {
                notifications.show({
                    title: 'Failed to save settings',
                    message: 'Please try again',
                    color: 'red',
                })
                return null;
            }

        }).then((resp) => {
            if (!resp) {
                return;
            }
            form.setInitialValues(values);
            form.setDirty({});
        });
    }
    return (
        <form onSubmit={form.onSubmit(saveSettings)}>
            <Grid>
                <Grid.Col span={12}>
                    <Fieldset legend="OPENADAPT">
                        <Stack>
                            <TextInput label="OPENADAPT_API_KEY" placeholder="Please enter your OpenAdapt API key" {...form.getInputProps('OPENADAPT_API_KEY')} />
                        </Stack>
                    </Fieldset>
                </Grid.Col>
                <Grid.Col span={12}>
                    <Text fz={20} mb={10} className='text-center'>
                        OR
                    </Text>
                </Grid.Col>
                <Grid.Col span={6}>
                    <Fieldset legend="PRIVACY">
                        <Stack>
                            <TextInput label="AWS_API_KEY" placeholder="Please enter your AWS API key" {...form.getInputProps('AWS_API_KEY')} />
                            <TextInput label="PRIVATE_AI_API_KEY" placeholder="Please enter your Private AI API key" {...form.getInputProps('PRIVATE_AI_API_KEY')} />
                        </Stack>
                    </Fieldset>
                </Grid.Col>
                <Grid.Col span={6}>
                    <Fieldset legend="SEGMENTATION">
                        <Stack>
                            <TextInput label="AWS_SEGMENT_API_KEY" placeholder="Please enter your AWS API key" {...form.getInputProps('AWS_SEGMENT_API_KEY')} />
                            <TextInput label="REPLICATE_API_KEY" placeholder="Please enter your Replicate API key" {...form.getInputProps('REPLICATE_API_KEY')} />
                        </Stack>
                    </Fieldset>
                </Grid.Col>
                <Grid.Col span={6}>
                    <Fieldset legend="COMPLETIONS">
                        <Stack>
                            <TextInput label="OPENAI_API_KEY" placeholder="Please enter your OpenAI API key" {...form.getInputProps('OPENAI_API_KEY')} />
                            <TextInput label="ANTHROPIC_API_KEY" placeholder="Please enter your Anthropic API key" {...form.getInputProps('ANTHROPIC_API_KEY')} />
                            <TextInput label="GOOGLE_API_KEY" placeholder="Please enter your Google API key" {...form.getInputProps('GOOGLE_API_KEY')} />
                        </Stack>
                    </Fieldset>
                </Grid.Col>
            </Grid>
            <Flex mt={40} columnGap={20}>
                <Button disabled={!form.isDirty()} type="submit">
                    Save settings
                </Button>
                <Button variant="subtle" disabled={!form.isDirty()} onClick={resetForm}>
                    Discard changes
                </Button>
            </Flex>
        </form>
    )
}